__author__ = 'spi'
# encoding: utf-8

import sys
import sqlite3
import struct
import os
import datetime
from argparse import ArgumentParser

class ColunasMsgStoreDB:
    def __init__(self,nome,tipo):
        self.nome = nome
        self.tipo = tipo

class MensagemMalFormada(RuntimeError):
   def __init__(self, arg):
      self.args = arg

class ColunaMensagemWhatsApp:
    def __init__(self,nomeTipo,codTipo,tamTipo,conteudo,tipoSqlite):
        self.nomeTipo = nomeTipo
        self.codTipo = codTipo
        self.tamTipo = tamTipo
        self.conteudo = conteudo
        self.tipoSqlite = tipoSqlite

def getColunasBancoOriginal(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(messages)")
    colunas = []
    for coluna in cursor:
        nome = coluna[1]
        tipo = coluna[2]
        colunaMsgStoreDB = ColunasMsgStoreDB(nome,tipo)
        colunas.append(colunaMsgStoreDB)
    return colunas

def getSQLCreateTable(cursor,nomeTabela):
    cursor.execute("SELECT sql FROM sqlite_master WHERE tbl_name = '" + nomeTabela + "' AND type = 'table'")
    for sql in cursor:
        return sql[0]

def createDB(conn,conn2):
    cursor = conn.cursor()
    cursor2 = conn2.cursor()
    createTable(cursor,getSQLCreateTable(cursor2,"messages"))
    createTable(cursor,getSQLCreateTable(cursor2,"chat_list"))

def createTable(cursor,sql):
    cursor.execute("" + sql + "")

def getConteudoPorTipo(coluna):
    try:
        if coluna.tipoSqlite == "TEXT":
            if coluna.tamTipo == 0:
                return None
            conteudoString = coluna.conteudo.decode("utf-8")
            return conteudoString
        elif coluna.tipoSqlite == "INTEGER":
            if coluna.conteudo[0] == 48: return 0
            elif coluna.conteudo[0] == 49: return 1
            else:
                conteudoInteger = int.from_bytes(coluna.conteudo, byteorder='big', signed=False)
                return conteudoInteger
        elif coluna.tipoSqlite in "REAL":
            return 0.0 #  Alterar
        else:
            return coluna.conteudo #  Alterar
    except:
        pass
    if coluna.nomeTipo == "data" or coluna.nomeTipo == "media_caption":
        return None
    return 0

def insertDB(listaColunas,conn):
    cursor = conn.cursor()
    dic = {}
    for coluna in listaColunas:
        dic[coluna.nomeTipo] = getConteudoPorTipo(coluna)
    columns = ', '.join(dic.keys())
    placeholders = ', '.join('?' * len(dic))
    columns = ', '.join(dic.keys())
    placeholders = ':'+', :'.join(dic.keys())
    query = 'INSERT INTO `messages` (%s) VALUES (%s)' % (columns, placeholders)
    if isTimestampValido(dic):
        cursor.execute(query, dic)
        conn.commit()

def isTimestampValido(dic):
    if dic["timestamp"] < 100000000000 or dic["timestamp"] > 2000000000000: # Verifica se as datas estao no periodo de 03/03/1973 e 18/05/2033
        return False
    if dic["data"] == None:
        if dic["received_timestamp"] < 100000000000 or dic["received_timestamp"] > 2000000000000: # Verifica se received timestamp esta entre as datas 03/03/1973 e 18/05/2033, caso nao haja mensagem escrita
            return False
    return True

def insertChatList(conn):
    cursor = conn.cursor()
    query = 'SELECT key_remote_jid FROM `messages` GROUP BY key_remote_jid'
    cursor.execute(query)
    keys = cursor.fetchall()
    for key_remote_jid in keys:
        insert = "INSERT INTO `chat_list` (key_remote_jid) VALUES ('" + key_remote_jid[0] +"')"
        cursor.execute(insert)
        conn.commit()

def getTamanhoCampo(tipoCampo):
    tamanhoCampo = 0
    if tipoCampo <= 11: # Inteiro (<= 11)
        if tipoCampo == 0:
            tamanhoCampo = 0
        elif tipoCampo < 5:
            tamanhoCampo = tipoCampo
        elif tipoCampo == 5:
            tamanhoCampo = 6
        elif tipoCampo == 7:
            tamanhoCampo = 8
        elif tipoCampo == 8:
            tamanhoCampo = 0
        elif tipoCampo == 9:
            tamanhoCampo = 0
    else: # BLOB ou TEXT (>= 12)
        tamanhoCampo = tipoCampo
        if tamanhoCampo % 2 == 0:
            tamanhoCampo = (tipoCampo - 12)/2
        else:
            tamanhoCampo = (tipoCampo - 13)/2
    return int(tamanhoCampo)

def decodeVarInt(stream):
    value = 0
    base = 1
    for raw_byte in stream:
        if (raw_byte & 0x80):
            base *= 128
    for raw_byte in stream:
        val_byte = raw_byte
        value += (val_byte & 0x7f) * base
        if (val_byte & 0x80):
            base /= 128
        else:
            break
    return int(value)

def recoveryMessages(data,conn,conn2):
    posicaoCursor = 0
    rshift = 0
    colunas = getColunasBancoOriginal(conn2)
    colunasWhatsApp = colunas[1:] # Remoção da coluna _id
    qtdCamposTotal = len(colunasWhatsApp)
    total = len(data) - qtdCamposTotal
    while(posicaoCursor < total):
        try:
            listaColunas = []
            for colunaMsgStoreDB in colunasWhatsApp:
                if data[posicaoCursor] < 127:
                    tipoCampo = data[posicaoCursor]
                    posicaoCursor += 1
                else: # Codificacao varint
                    posicaoCursorInicioStream = posicaoCursor
                    while (data[posicaoCursor] > 127) and (posicaoCursor < total):
                        posicaoCursor += 1
                    if (posicaoCursor - posicaoCursorInicioStream) > 8:
                        raise MensagemMalFormada("Mensagem mal formada!")
                    tipoCampo = decodeVarInt(data[posicaoCursorInicioStream:posicaoCursor+1])
                    posicaoCursor += 1 # necessário andar com cursor
                colunaMensagemWhatsApp = ColunaMensagemWhatsApp(colunaMsgStoreDB.nome,tipoCampo,getTamanhoCampo(tipoCampo),None,colunaMsgStoreDB.tipo)
                listaColunas.append(colunaMensagemWhatsApp)
            getConteudos(data, listaColunas, posicaoCursor)
            coluna = listaColunas[0] # Analisa coluna com os dados do key_remote_jid
            if coluna.nomeTipo == 'key_remote_jid':
                tamanhoConteudoKeyRemoteJid = len(coluna.conteudo)
                if tamanhoConteudoKeyRemoteJid >= 27 and tamanhoConteudoKeyRemoteJid <= 29:
                    if contemStringKeyRemoteJidDeGrupo(coluna,tamanhoConteudoKeyRemoteJid):
                        insertDB(listaColunas,conn)
                    elif contemStringKeyRemoteJid(coluna,tamanhoConteudoKeyRemoteJid):
                        insertDB(listaColunas,conn)
        except (UnicodeDecodeError,MensagemMalFormada):
            pass
        except:
            print("Unexpected error:", sys.exc_info()[0])
        rshift += 1
        posicaoCursor = rshift


def getConteudos(data, listaColunas, posicaoCursor):
    for coluna in listaColunas:
        tamanho = coluna.tamTipo
        tipo = coluna.codTipo
        if (tipo == 8 or tipo == 0):
            coluna.conteudo = b'0'
        elif tipo == 9:
            coluna.conteudo = b'1'
        else:
            coluna.conteudo = data[posicaoCursor:(posicaoCursor + tamanho)]
            posicaoCursor = posicaoCursor + tamanho


def contemStringKeyRemoteJid(coluna,tamanhoConteudoKeyRemoteJid):
    if coluna.conteudo.decode('ascii').find("@s.whatsapp") != -1:
        if( (coluna.conteudo[0] == 53) and (coluna.conteudo[1] == 53) ): # Verifica se o numero comecao com 55 (código do Brasil)
            if( (coluna.conteudo[tamanhoConteudoKeyRemoteJid-1] == 116) and (coluna.conteudo[tamanhoConteudoKeyRemoteJid-2] == 101) and (coluna.conteudo[tamanhoConteudoKeyRemoteJid-3] == 110)):  # Verifica se a string termina com net
                return True
    return False

def contemStringKeyRemoteJidDeGrupo(coluna,tamanhoConteudoKeyRemoteJid):
    if coluna.conteudo.decode('ascii').find("@g.us") != -1:
        if( (coluna.conteudo[0] == 53) and (coluna.conteudo[1] == 53) ): # Verifica se o numero comecao com 55 (código do Brasil)
            if( (coluna.conteudo[tamanhoConteudoKeyRemoteJid-1] == 115) and (coluna.conteudo[tamanhoConteudoKeyRemoteJid-2] == 117)):  # Verifica se a string termina com us
                return True
    return False

def sqliteParser(conn,conn2,basepath):
    #
    #  **** Código-fonte adaptado de https://github.com/mdegrazia/SQLite-Deleted-Records-Parser ****
    #
    try:
        f = open(basepath, "rb")
    except:
        print("Arquivo não encontrado!")
        exit(0)

    filesize = len(f.read())
    f.seek(0)
    header = f.read(16)
    sHeader = header.decode("utf-8")
    if (sHeader.find("SQLite") == -1):
        print("Arquivo não suportado!")
        exit(0)

    pagesize = struct.unpack('>H', f.read(2))[0]
    offset = pagesize
    while offset < filesize:
        f.seek(offset)
        flag = struct.unpack('>b', f.read(1))[0]
        if flag == 13:
            freeblock_offset = struct.unpack('>h', f.read(2))[0]
            num_cells = struct.unpack('>h', f.read(2))[0]
            cell_offset = struct.unpack('>h', f.read(2))[0]
            num_free_bytes = struct.unpack('>b', f.read(1))[0]
            start = 8 + (num_cells * 2)
            length = cell_offset - start
            f.read(num_cells * 2)
            unallocated = f.read(length)
            recoveryMessages(unallocated,conn,conn2)
            while freeblock_offset != 0:
                f.seek(offset + freeblock_offset)
                next_fb_offset = struct.unpack('>h', f.read(2))[0]
                free_block_size = struct.unpack('>hh', f.read(4))[0]
                f.seek(offset + freeblock_offset)
                free_block = f.read(free_block_size)
                recoveryMessages(free_block,conn,conn2)
                freeblock_offset = next_fb_offset
        offset = offset + pagesize

def main(argv):
    print("Iniciando recuperação de mensagens apagadas!")
    print(datetime.datetime.now())
    # parser options
    parser = ArgumentParser(description='Recuperação de mensagens apagadas do WhatsApp')
    parser.add_argument(dest='infile', help="A entrada deve ser o banco 'msgstore.db'")
    options = parser.parse_args()
    # checks for the input file
    if options.infile is None:
        parser.print_help()
        sys.exit(1)
    if not os.path.exists(options.infile):
        print('Error: "{0}" Arquivo não encontrado!'.format(options.infile))
        sys.exit(1)
    with open(options.infile, "rb") as f:
        descriptor_bytes = f.read(15)
        expected_descriptor_bytes = b"SQLite format 3"
        if descriptor_bytes == expected_descriptor_bytes:
            print("SQLite database detectado")
        else:
            print('Error: arquivo não é um banco SQLite'.format(options.infile))
            sys.exit(1)
    db_saida = options.infile + "_MSGS_RECUPERADAS.db"
    conn = sqlite3.connect(db_saida)
    conn2 = sqlite3.connect(options.infile)
    createDB(conn,conn2)
    sqliteParser(conn,conn2,options.infile)
    insertChatList(conn)
    conn.close()
    conn2.close()
    print("Processo finalizado. Mensagens apagadas disponíveis no arquivo " + db_saida)
    print(datetime.datetime.now())
if __name__ == '__main__':
    main(sys.argv[1:])


