# msgstoreRecoverySPI
Ferramenta para recuperação de mensagens do aplicativo WhatsApp nas regiões de Freeblock e Unallocated do banco SQLite.

## Trabalho acadêmico
O script é resultado do trabalho acadêmico "Método de recuperação de mensagens apagadas do SQLite no contexto do aplicativo WhatsApp para plataforma Android", disponível em http://icofcs.org/2015/ICoFCS-2015-006.pdf.

O código desenvolvido foi adaptado do projeto SQLite-Parser, disponível em https://github.com/mdegrazia/SQLite-Deleted-Records-Parser.

É importante ressaltar que as mensagens localizadas não necessariamente são mensagens apagadas pelo usuário, visto que o aplicativo replica algumas mensagens em determinadas ocasiões.
Além disso, o script somente recupera as mensagens bem formadas  compatíveis com a estrutura da tabela "Messages", ou seja, aquelas que possuem dados compativeis com os tipos das colunas da tabela.
Para recuperação de fragmentos de string, recomenda-se adaptar o script para recuperar toda a estrutura de freeblock e unallocated buscando-se por expressões textuais.

## Uso
O script recebe como parâmetro de entrada o banco de dados SQLite do WhatsApp (para aplicativos Android) e percorre as páginas folha do banco em busca de mensagens bem formadas nas regiões freeblock e unallocated.

Como resultado, é criado um novo banco de dados SQLite cotendo somente as mensagens bem formadas encontradas nas referidas regiões.

> Ex: python3 msgstoreRecoverySPI.py msgstore.db


### Contact

* [twitter](https://twitter.com/jpclaudino)
* E-mail: jpclaudino@gmail.com