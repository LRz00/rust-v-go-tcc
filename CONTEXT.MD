Mapa TCC
Como diferenças de design (gerenciamento de memória e modelo de concorrência) em Go e Rust influenciam desempenho e escalabilidade de aplicações backend, e como isso se relaciona com a adoção pelas comunidades e organizações?
Subperguntas (bem operacionalizáveis)
Adoção e popularidade (sociotécnico):
 Quais fatores técnicos e sociotécnicos são mais citados na literatura e em indicadores públicos para explicar a adoção de Go e Rust?


Desempenho (técnico/empírico):
 Qual o efeito do GC + goroutines (Go) versus ownership/borrowing + runtime async (Rust) em latência (p95/p99), throughput e uso de recursos em um backend controlado?


Escalabilidade e “estabilidade” (técnico/empírico):
 Como cada linguagem se comporta ao aumentar progressivamente conexões simultâneas (curvas de saturação), e qual apresenta maior estabilidade de serviço medida por variabilidade de latência, taxa de erro e interrupções?


Observação: “O que torna popular” e “vantagens/desvantagens” viram parte da Subpergunta (1) e do Cap. 2/3. Assim, você evita perguntas descritivas repetidas.
O que exatamente medir (para ficar “observável”)
Em ambos:
RSS (memória real do processo) e seu crescimento ao longo do tempo.
Heap atual (tamanho do heap/uso interno).
Taxa de alocação (bytes alocados por segundo / por requisição).
Objetos vivos (quando aplicável) e picos.
Overhead por concorrência (muitas conexões/goroutines/tasks).
Impacto na latência: p95/p99 quando a pressão de memória aumenta.
Ferramentas de medição:
RSS:
Go: utilizar /proc/self/statm no linux ou ps -o pid,rss,command -p <PID>.
Rust: mesma coisa (existe um crate, mas melhor padronizar)
Heap atual:
Go: runtime.memStats (nativo)
Rust: não possui garbage collector -> crate jemalloc
Taxa de alocação:
Go: mesma coisa de acima
Rust: mesma coisa de acima.
Objetos vivos:
Go: HeapObjects (nativo)
Rust: não é possivel medir diretamente
latencia:
go: wrk
Rust: wrk
overhead: wrk -> Fixar o trabalho e variar apenas o nível de concorrência.

Objetivo geral
Analisar como diferenças de design relacionadas ao gerenciamento de memória e ao modelo de concorrência em Go e Rust influenciam o desempenho e a escalabilidade de aplicações backend, e como esses aspectos se relacionam com padrões de adoção observados na literatura e em indicadores públicos da comunidade e da indústria.

Objetivos específicos
Mapear, por meio de revisão de literatura, os principais fatores técnicos e sociotécnicos associados à adoção de Go e Rust (por exemplo: produtividade, curva de aprendizado, maturidade de ferramentas, suporte corporativo, disponibilidade de bibliotecas, segurança, desempenho, empregabilidade e legitimidade institucional).


Sistematizar as diferenças de design entre Go e Rust relevantes para backend, com foco em:
 a) gerenciamento de memória (GC em Go; ownership/borrowing e ausência de GC em Rust);
 b) concorrência (goroutines/channels em Go; threads seguras e runtime async em Rust);
 c) implicações esperadas sobre previsibilidade de latência, throughput e consumo de recursos.


Implementar um backend controlado e funcionalmente equivalente em Go e em Rust (mesmos endpoints, payloads, e comportamento), assegurando comparabilidade experimental (mesmo ambiente de execução, carga, e parâmetros).


Mensurar e comparar desempenho entre as implementações, utilizando métricas de latência (p95/p99), throughput e uso de recursos (CPU, memória/RSS e, quando aplicável, métricas específicas do runtime/GC), em cenários controlados de carga.


Avaliar escalabilidade e estabilidade de serviço por meio de experimentos com aumento progressivo de conexões simultâneas, identificando curvas de saturação e comparando:
 a) variabilidade de latência (ex.: dispersão do p95/p99 entre repetições);
 b) taxa de erro (timeouts/5xx);
 c) ocorrência de interrupções (crashes, OOM, degradações abruptas).


Relacionar os resultados empíricos (desempenho/escalabilidade) aos achados da revisão e aos indicadores públicos de adoção, discutindo convergências e divergências entre “percepção de valor”, “evidência técnica” e “adoção prática”.

Hipóteses (testáveis e alinhadas às métricas)
H1 — Tail latency e previsibilidade sob pressão de alocação
Em cenários com maior pressão de alocação de memória, a implementação em Rust apresentará menor p99 e menor variabilidade do p99 em comparação à implementação em Go, devido à ausência de pausas associadas ao garbage collector e ao gerenciamento determinístico por escopo (RAII/ownership).
H2 — Throughput e concorrência em carga moderada
Em níveis baixos a moderados de concorrência, a implementação em Go apresentará throughput igual ou superior à de Rust, em razão do modelo de goroutines e do runtime consolidado para multiplexação de tarefas concorrentes, mantendo overhead reduzido de criação/agendamento.
H3 — Ponto de saturação e degradação com aumento de conexões
À medida que o número de conexões simultâneas aumenta, Go e Rust exibirão pontos de saturação distintos; espera-se que Rust mantenha crescimento mais estável até níveis mais altos de concorrência (menor “degrau” de degradação), refletido por crescimento menos abrupto do p99 e menor aumento da taxa de erro próximo ao limite de capacidade.
H4 — Uso de memória e comportamento de heap/RSS
Sob a mesma carga, Go exibirá maior crescimento do heap/RSS e/ou maior oscilação associada a ciclos de GC em cenários allocation-heavy, enquanto Rust tenderá a apresentar perfil mais estável de memória, embora possa variar conforme o padrão de alocação e o allocator utilizado.
H5 — Adoção: trade-off produtividade versus garantias de segurança
A análise sociotécnica indicará que Go é mais associado a fatores de adoção ligados à produtividade, simplicidade e facilidade de manutenção/contratação, enquanto Rust é mais associado a segurança de memória, robustez e desempenho previsível, o que ajuda a explicar cenários em que Rust é altamente “admirada”, mas Go é mais amplamente adotada em aplicações backend generalistas.

Introdução
Contexto 
A seleção de uma linguagem de programação constitui uma etapa fundamental no processo de desenvolvimento de um sistema pois influencia diretamente a adequação tecnológica ao problema, o ambiente de execução e os caminhos possíveis para a evolução futura do sistema. Diversos fatores podem impactar essa escolha, e nem todos eles são puramente técnicos (como a performance, considerando o número de usuários finais, a confiabilidade). Na verdade, fatores sociais e de ecossistema assumem maior influência do que os aspectos puramente técnicos. A disponibilidade de bibliotecas, ferramentas, frameworks e a familiaridade dos desenvolvedores com determinada tecnologia tem grande impacto nessa escolha.
 
Nenhuma linguagem de programação é a melhor para todos os cenários, é inclusive possível de se ver que diante das milhares existentes, poucas poucas dominam amplamente o mercado enquanto muitas permanecem restritas a nichos específicos
Além disso, o interesse e a utilização de linguagens variam com o tempo; observando o mundo do desenvolvimento de software é possível ver registros de aumento gradual no uso de determinadas linguagens seguido de declínio em períodos posteriores. Em análises de grandes repositórios de código aberto, linguagens como JavaScript, Java e Python permanecem entre as mais populares, enquanto outras como Go e Rust surgem como opções relevantes e em crescimento. O desenvolvimento moderno também adota frequentemente mais de uma linguagem no mesmo projeto.

Torna-se então essencial entender o que motiva e influencia os trends de desenvolvimento em uma indústria tão dinâmica. 

Nesse contexto de constante evolução tecnológica, duas linguagens em especial têm se destacado nos últimos anos: Go e Rust. Ambas surgiram com o propósito de oferecer alternativas mais seguras e eficientes para o desenvolvimento de software de alto desempenho, historicamente dominado por C e C++.

Rust é uma linguagem de programação de sistemas de código aberto (open-source systems programming language) criada pela Mozilla. Seu primeiro lançamento estável ocorreu em 2014. Ela foi desenvolvida com o objetivo de combater vulnerabilidades comuns e potencialmente graves relacionadas à segurança de memória (Fulton et al., 2021). Ela é uma linguagem multi-paradigma (multi-paradigm language), incorporando elementos de linguagens funcionais, imperativas e orientadas a objetos, promovida por prevenir falhas de segmentação e garantir a segurança de threads Ela se encaixa em ambientes com restrições de recursos por possuir um modelo de memória seguro sem garbage collector e oferece zero cost abstractions, permitindo que o desenvolvedor use recursos de alto nível sem comprometer o desempenho da aplicação  (Blandy; Orendorff; Tindall, 2021). 

Já Go é uma linguagem de programação criada pela Google com foco em simplicidade, eficiência e escalabilidade, visando superar limitações encontradas em linguagens tradicionais em grandes bases de código. Ela começou como um projeto paralelo (side project) por Rob Pike, Robert Griesemer e Ken Thompson motivados por sua insatisfação com as linguagens e ambientes de desenvolvimento existentes que não escalavam bem para a enorme base de código e o esforço de engenharia da Google. A linguagem adota um modelo pragmático que incentiva o código simples e direto, possuindo um coletor de lixo que reduz a carga de gerenciamento manual da memória e facilita o aprendizado. Apesar de suportar conceitos de orientação a objetos, Go utiliza interfaces com satisfação implícita, promovendo baixo acoplamento e componentes com responsabilidades menores. A linguagem possui também um modelo de concorrência robusto, permitindo paralelismo eficiente com baixo consumo de recursos, o que a torna adequada para sistemas distribuídos e aplicações de alta performance (Meyerson, 2014).

Objetivos
Essa pesquisa tem como objetivo avaliar os fatores que levam a crescente popularidade das linguagens de programação Rust e Go, por meio de análise dos diferenciais técnicos de cada língua, resultados de casos de estudo, e indicadores empíricos de adoção e crescimento.

Objetivos Específicos

Para a realizar esse objetivo, esse trabalho pretende:
Identificar os fatores que levam a escolha dessas linguagens para desenvolvedores e empresas, considerando aspectos técnicos e sociais. 
Levantar dados a partir da literatura existente sobre os principais aspectos técnicos, vantagens e desvantagens associados às linguagens Rust e Go.
Entender quais aspectos levam a escolha de Rust ou Go como linguagem principal de um projeto.


Justificativa

Desde o ano de 2017 a empresa Jetbrains anualmente realiza uma pesquisa visando mapear o estado do mundo do desenvolvimento; a pesquisa tem como objetivos, entre muitos, identificar ferramentas e linguagens de programação mais utilizadas, os tipos de aplicações desenvolvidas etc. Um dos campos mapeados por essa pesquisa é quais linguagens de programação os desenvolvedores têm a intenção de adotar em futuros projetos, bem como um campo que combina estabilidade de crescimento, impulso a adoção, e lealdade de usuários, com o objetivo de identificar as linguagens com mais chances de expansão nos anos seguintes, chamado de “Promise Index”

Em 2024, as linguagens de programação com mais intenção de adoção foram Go e Rust com 10% e 11% respectivamente. Quanto ao promise index, Rust ocupava o 2º lugar, enquanto Go ocupava o 4º (“Software Developers Statistics 2024 - State of Developer Ecosystem Report”, 2024). Enquanto em 2025, ambas foram novamente as duas linguagens com mais intenção de adoção, apenas trocando de posição, Go dessa vez ocupava o primeiro lugar com 11% e Rust o segundo com 10%. No promise index, ambas mantiveram suas posições do ano anterior. (“Tools and Trends - The State of Developer Ecosystem in 2025”, 2025)

De forma similar, o site de perguntas e respostas Stack Overflow também realiza uma série de enquetes de forma anual. Nessa enquete há uma seção que mede admiração versus desejo, sendo admiração entendido como usuários que utilizaram a linguagem e pretendem seguir utilizando-a, e desejo como usuários que pretendem, ou possuem inclinação a utilizar a linguagem no futuro.

Em 2024, Rust foi a linguagem mais admirada com uma pontuação de 83%, enquanto Go possuía uma pontuação de 67% (“Technology | 2024 Stack Overflow Developer Survey”, 2024). Já em 2025 Rust continuou sendo a a linguagem mais admirada, com 72%, enquanto Go caiu para 57%  (“Technology | 2025 Stack Overflow Developer Survey”, 2025).
 
Sendo ambas linguagens que surgiram relativamente recentemente–quando comparado por exemplo com Python, que ocupa o primeiro lugar do Promise index de 2025–e sendo ambas popularmente caracterizadas por possuírem bom desempenho e alta segurança, bem como com esse dados, essa pesquisa visa investigar os motivos da crescente popularidade dessas duas linguagens, identificando seus pontos positivos e negativos listados em literatura existente, bem como analisar o crescimento de sua popularidade por meio de dados empíricos.

Organização

Ao decorrer deste trabalho investigaremos os motivos que levam à adoção e aumento na popularidade dessas linguagens de programação. No capítulo 2, a Fundamentação Teórica está dividida em 3 partes: primeiro, discutiremos os critérios que influenciam a escolha de linguagens de programação, abrangendo impactos no design do software, no ambiente organizacional e no comportamento dos desenvolvedores. Em seguida, são analisadas métricas de popularidade e adoção. E concluímos destacando as características técnicas de Go e Rust, sintetizando seus diferenciais e limitações.
O Capítulo 3 realiza uma análise comparativa entre as duas linguagens, relacionando aspectos técnicos com os fatores que motivam a adoção, incluindo sua aceitação em contextos industriais e comunitários. O Capítulo 4 descreve a metodologia adotada para a obtenção e interpretação dos dados utilizados na pesquisa. No Capítulo 5, são apresentados os resultados e a discussão, abordando o crescimento recente das linguagens, possíveis explicações para mudanças de interesse e diferenças entre percepção de valor e adoção prática. Por fim, o Capítulo 6 apresenta as conclusões, destacando os principais achados, limitações identificadas e sugestões para estudos futuros sobre a evolução tecnológica e o processo de adoção de linguagens de programação.




Fundamentação teórica.

Linguagens de Programação e o Desenvolvimento de Sistemas Modernos
Uma linguagem de programação é uma ferramenta essencial para o desenvolvimento de software, composta por um conjunto de instruções utilizadas para se comunicar com o computador e permitir que a máquina execute uma série de tarefas. Inicialmente, as instruções eram passadas diretamente à máquina em sua própria linguagem — formada inteiramente por 0s e 1s (Nerlove, 2004).

A primeira linguagem de programação como a entendemos hoje, legível por humanos e compreendida pela máquina, foi a Assembly, que tornava a programação ligeiramente mais simples, embora ainda fosse uma linguagem de baixo nível. Ela representava uma tradução quase direta da linguagem de máquina, exigindo do programador um alto conhecimento sobre a arquitetura do hardware (Kumar, Kaur, Singh, 2025). A partir dessa evolução, observa-se uma tendência contínua de abstração, que culmina nas linguagens de alto nível, desenvolvidas para permitir que o programador se concentre mais na lógica do software e menos nos detalhes da máquina (Nerlove, 2004). Tal processo está diretamente relacionado ao aumento da produtividade e facilidade de adoção de novas linguagens.

O equilíbrio entre abstração e controle foi alcançado com a linguagem C, que combina um alto nível de abstração com o controle e a precisão das instruções típicas das linguagens de baixo nível. O código escrito em C mostrou-se eficiente a nível de sistema, mantendo-se relativamente independente do hardware em que era executado (Kumar, Kaur, Singh, 2025). Essa linguagem também teve grande influência na mudança dos paradigmas da programação, sendo a base para o surgimento da orientação a objetos com o C++, uma extensão da linguagem original que introduziu conceitos como classes, herança e polimorfismo (Nerlove, 2004). Tais mudanças mostram como novos paradigmas surgem para atender necessidades específicas da indústria, de forma semelhante ao que ocorre com Rust e Go em relação à segurança, concorrência e escalabilidade.

Um paradigma é um modelo ou método de abordagem utilizado para a resolução de problemas. Na programação, os paradigmas servem como modelos de abstração e organização de código (Michaelson, 2018). Entre os principais paradigmas estão a programação orientada a objetos, orientada a eventos e funcional. A escolha de qual paradigma seguir depende do tipo de aplicação e de seus objetivos, pois cada um apresenta pontos fortes e fracos distintos (Farxodjon O‘g‘li, 2024).

Da mesma forma, a seleção de uma linguagem de programação é uma decisão estratégica e técnica fundamental no início do desenvolvimento de software, pois influencia diretamente o processo de criação, manutenção e evolução do sistema ao longo do tempo (O’Connor, 2003). Essa decisão envolve diversos critérios relacionados ao projeto, como disponibilidade de desenvolvedores, documentação e adequação da linguagem ao ambiente e às necessidades da aplicação (Farshidi; Jansen; Deldar, 2021). Não existe uma linguagem universalmente superior para todos os cenários, uma vez que a escolha depende das prioridades e do contexto organizacional em que o software será desenvolvido (Farshidi; Jansen; Deldar, 2021).

O porte organizacional também exerce influência significativa nessa decisão. Estudos indicam que, à medida que o tamanho da empresa aumenta, bibliotecas comerciais tendem a adquirir maior relevância, assim como a confiabilidade do software. Em contrapartida, aspectos como simplicidade e velocidade de desenvolvimento tornam-se relativamente menos prioritários. Além disso, o nível de experiência dos desenvolvedores e a presença de código legado passam a ter impacto mais significativo em organizações de maior porte (Meryerovich; Rabkin, 2013). Para as empresas, a familiaridade da equipe com a linguagem escolhida e a ampla disponibilidade de bibliotecas que cobrem diversos casos de uso são fatores determinantes (Pang; Anslow; Noble, 2018).

No que diz respeito à preferência individual dos desenvolvedores, a pesquisa mostra que a simplicidade de uma linguagem,  uma sintaxe mais compreensível, não é necessariamente o fator mais atrativo para a maioria dos programadores (Meryerovich; Rabkin, 2013). Entre outros fatores que tornam uma linguagem atraente para desenvolvedores estão a existência de bibliotecas, desempenho e herança (Meryerovich; Rabkin, 2013).

Quanto à tipagem, o uso de linguagens estaticamente tipadas é fortemente enraizado entre os programadores, sendo mais valorizado especialmente por profissionais com mais anos de experiência (Pang; Anslow; Noble, 2018). 

Entretanto, em muitos casos, a escolha da linguagem não cabe diretamente ao desenvolvedor, sendo de responsabilidade da gerência ou de um líder técnico da equipe (Pang; Anslow; Noble, 2018).

Entretanto, a escolha nem sempre é feita pelo desenvolvedor, mas pela gerência ou lideranças técnicas (Pang; Anslow; Noble, 2018). Isso ressalta a importância de alinhar as características da linguagem com as necessidades da organização, especialmente em um cenário de arquiteturas distribuídas, microserviços e uso extensivo de containers, que ampliam a complexidade e exigem maior segurança e escalabilidade (Winkfield; Hu; Hoppa, 2018). Nesse contexto, Rust e Go surgem como respostas modernas a esses desafios.

Linguagens de Programação de Alto Desempenho e Segurança
Tratando-se da evolução das linguagens de programação, uma das mudanças que se notam é um foco na segurança das aplicações; enquanto linguagens com C e C++ tinham a memória gerenciada manualmente pelo programador, o que faz com que a maioria das vulnerabilidades críticas encontradas nessas linguagens fossem causadas por problemas de segurança de memória, como como use-after-free, que ocorre quando o programa tenta acessar uma área de memória que já foi liberada, e buffer overflow, que acontece quando são gravados mais dados do que o espaço de memória reservado, fazendo com que informações “transbordem” para outras áreas. (Fulton et al., 2021).

Em contraste, linguagens modernas implementam segurança de forma proativa, buscando evitar vulnerabilidades por meio de segurança de memória e tipagem estática (Viitanen, 2025). E mesmo que a implementação dessas estratégias de segurança, tenda a aumentar o tempo de compilação das aplicações, com um tempo de build mais longo, esse aumento no tempo de compilação é compensado por maior confiabilidade, pois uma vez que o código foi compilado os desenvolvedores se sentem mais seguros em acreditar que o código está correto e seguro. (Fulton et al., 2021).
GO.
Go é uma linguagem de programação criada pela Google, sua criação foi motivada pela insatisfação dos desenvolvedores com as linguagens e ambientes de desenvolvimento existentes que não escalavam bem para a enorme base de código e o esforço de engenharia da Google (Meyerson, 2014). Ela é considerada uma linguagem com foco em produtividade e foi projetada para ser relativamente simples, e não possui alguns recursos que outras linguagens possuem, o que torna os programas escritos em go simples, diretos e pragmáticos.(Arundel, 2024)

Go é uma linguagem orientada a objetos mas não possui o conceito de classes, nem o de herança no sentido tradicional. A orientação a objetos em Go é implementada através de interfaces, sendo uma característica notável dessas interfaces, a implementação implícita, sem a necessidade de usar palavras chaves como ‘implements’ como em outras linguagens. (Meyerson, 2014).Go é estaticamente e fortemente tipada. O compilador verifica os tipos de variáveis, ajudando a prevenir erros. (Meyerson, 2014).

Tratando-se de performance, Go é capaz de superar muitas linguagens e ser comparável com a performance de C (Altherwi, 2019).  Esse desempenho está relacionado ao modelo de concorrência da linguagem chamado de Goroutines, que são estruturas leves semelhantes a threads, mas muito mais eficientes. Uma thread é uma unidade básica de execução dentro de um processo, responsável por realizar tarefas de forma independente, podendo rodar em paralelo com outras threads. No entanto, cada thread tradicional consome memória e recursos do sistema operacional, o que limita a quantidade que pode ser criada. Já as Goroutines são versões extremamente leves dessas threads, gerenciadas pelo próprio tempo de execução do Go, o que permite criar milhares delas sem causar sobrecarga significativa. Isso é possível graças à multiplexação, processo em que várias Goroutines são executadas sobre um número menor de threads do sistema, geralmente equivalente ao número de núcleos do processador, garantindo melhor uso do paralelismo. Além disso, a comunicação entre Goroutines é feita por meio dos canais (channels), que funcionam como “tubos” por onde os dados passam de uma rotina para outra, permitindo sincronização e troca segura de informações. Esse modelo proporciona uma concorrência de alto desempenho e uma escrita de código mais simples e direta, sem a necessidade de lidar com estruturas complexas de callbacks, tornando o Go ideal para sistemas distribuídos e aplicações de alta escalabilidade. (Meyerson, 2014).


Rust
Rust é uma linguagem de programação de sistemas de código aberto criada pela Mozilla, com o objetivo de combater vulnerabilidades comuns e potencialmente graves relacionadas à segurança de memória(Fulton et al., 2021).

O principal objetivo de Rust como uma linguagem de programação é garantir a segurança, sendo a primeira linguagem a superar os trade-offs entre a segurança que as linguagens de baixo nível fornecem, e o controle de recurso das linguagens de alto nível. Isso é possível utilizando um sistema de tipagem forte baseado nos conceitos de Ownership e Borrowing,  que gerencia a alocação e desalocação de memória (e de outros recursos) e proíbe a mutação de estado compartilhado. No Rust, cada valor possui um único dono que controla por quanto tempo ele existe no programa; quando esse dono sai do escopo, o valor é liberado automaticamente da memória. Esse modelo impede erros comuns, como acessar um dado que já foi liberado (use-after-free) ou tentar liberar o mesmo recurso duas vezes (double free), tudo isso sem depender de um coletor de lixo rodando em segundo plano. (Jung et al, 2021)

Rust alcança desempenho comparável a C e C++, com a diferença de que Rust possui gerenciamento de memória automático e segurança forçada pelo compilador.  A segurança de Rust é alcançada no mesmo nível de abstração que C e C++, mas a responsabilidade dessa segurança é transferida do programador (C/C++) para o compilador (Rust) (Blandy; Orendoff; Tindall, 2021). Isso é feito sem perder o desempenho:  resultados experimentais mais recentes de benchmarking mostram que o Rust supera Java e Python e consegue acompanhar C e C++. Em testes específicos de CPU time, o Rust foi o líder em dois dos três algoritmos testados, perdendo apenas por uma pequena margem para C e C++ no terceiro. (Bugden; Ayman; Alahmar, 2022).

Rust é ideal para uso em sistemas de baixo nível onde “cada byte importa” (Blandy; Orendoff; Tindall, 2021), como o desenvolvimento de kernels e sistemas operacionais, drivers de dispositivos, sistemas de gerenciamento de máquinas virtuais, sistemas embarcados e IoT( Internet das coisas) e software de clouds. (Fulton et al, 2021)

A principal vantagem do Rust é sua forte garantia de segurança sem abrir mão do desempenho, alcançando um equilíbrio que tradicionalmente era difícil em linguagens de sistemas. No entanto, esse benefício vem acompanhado de uma curva de aprendizado elevada, e muitos desenvolvedores consideram o Rust mais desafiador de dominar do que outras linguagens, conforme apontado por Fulton et al. (2021).
Go vs Rust

As linguagens de programação Rust e Go foram desenvolvidas em períodos relativamente próximos, ambas com a intenção de oferecer alternativas modernas ao C e C++, mantendo foco em velocidade e segurança, tanto em tipagem quanto em gerenciamento de memória (Fulton et al, 2021). Contudo, apesar de partilharem objetivos semelhantes, cada uma adota estratégias distintas para alcançá-los. Diferentemente do Rust, o Go utiliza um Garbage Collector, projetado para ser previsível e minimizar a produção de “lixo” durante a execução. Embora também seja considerada uma linguagem segura, Go permite acesso não sincronizado à memória compartilhada, algo que o modelo de segurança do Rust proíbe. Em termos de desempenho, ambas são altamente eficientes,sendo comparadas a performance de C e C++ (Altherwi, 2019)  (Bugden; Ayman; Alahmar, 2022).

No campo da concorrência, as duas linguagens também seguem caminhos diferentes. Go oferece um modelo baseado em goroutines, threads leves multiplexadas sobre threads do sistema operacional, e channels, que são canais tipados de comunicação entre essas rotinas. Já o Rust adota o princípio da concorrência segura (trustworthy concurrency), no qual o sistema de tipos garante que threads só possam compartilhar memória de formas que evitam data races, ou seja, acessos assíncronos e não controlados a dados compartilhados.

Tratando-se de comunidade e bibliotecas, quase todo projeto em Go é estruturado como um pacote, ou bibliotecas de pacotes relacionados, que pode ser facilmente importado e reutilizado em outros projetos. De acordo com Arundel (2024), seja qual for a funcionalidade desejada, é provável que alguém já tenha desenvolvido um pacote adequado, tornando o trabalho do desenvolvedor muito mais voltado à integração desses módulos do que à implementação completa do zero.

No caso do Rust, algo semelhante ocorre: a linguagem possui um ecossistema amplo de pacotes, chamados crates. O registro oficial da comunidade, o crates.io, já reúne mais de 200 mil crates, oferecendo uma grande variedade de soluções para diferentes necessidades (“crates.io: Rust Package Registry”, [s.d.]).
Todas essas diferenças influenciam diretamente os motivos pelos quais desenvolvedores adotam uma ou outra linguagem. Rust é preferido em contextos de baixo nível, enquanto Go é amplamente utilizado em vários cenários, onde a necessidade de controle de memória é menor. Essa distinção entre áreas de aplicação também impacta os números de popularidade observados na prática.

Popularidade e Adoção.

Existem diversas maneiras de avaliar a popularidade e o nível de uso de uma linguagem de programação. Uma delas é observar pesquisas e enquetes realizadas por empresas de grande porte, que reúnem dados estatísticos diretamente da comunidade de desenvolvedores. Outra forma é analisar indicadores objetivos, como o número de repositórios públicos, contribuições em projetos open-source e atividade em plataformas de colaboração. Esses elementos, quando combinados, oferecem uma visão mais completa do impacto e da adoção real de cada linguagem.

Entre os sites e organizações que realizam levantamentos periódicos sobre linguagens de programação, destaca-se o Stack Overflow — um dos maiores sites de perguntas e respostas da área — que publica anualmente o Stack Overflow Developer Survey, consolidando dados de centenas de milhares de desenvolvedores. A JetBrains, empresa conhecida por suas ferramentas de desenvolvimento, também produz anualmente o relatório State of Developer Ecosystem, que analisa tendências de uso, ferramentas e ecossistemas. Já a RedMonk, empresa especializada em análise da indústria de software, divulga relatórios ocasionais que correlacionam atividade no GitHub e discussões no Stack Overflow para medir a popularidade das linguagens. Por fim, o Índice TIOBE, mantido pela empresa de qualidade de software TIOBE, apresenta um ranking mensal baseado em métricas como buscas em mecanismos populares, número de engenheiros disponíveis e oferta de cursos, servindo como mais um indicador amplamente consultado no setor.

A partir desses indicadores, torna-se possível observar como a indústria e os desenvolvedores reagem ao surgimento e à consolidação de novas linguagens de programação, acompanhando seu desempenho nessas pesquisas ao longo do tempo e analisando como elas se posicionam em relação a linguagens mais antigas e amplamente estabelecidas.

Por exemplo, em 2015, na pesquisa do Stack Overflow, tanto Rust quanto Go ainda não figuravam entre as linguagens mais populares, embora já aparecessem entre as mais apreciadas pelos desenvolvedores. Uma década depois, em 2025, o cenário mudou significativamente: ambas passaram a integrar o ranking das linguagens mais populares(superando numericamente algumas que estavam à frente em 2015), com Rust mantendo-se, inclusive, como a linguagem mais admirada da pesquisa.

Existem muitos fatores sociais e técnicos que influenciam a adoção e popularidade de linguagens mais novas como o Rust e o Go. Elas tendem a chegar no mercado com promessas de inovações, com seus designers e usuários iniciais fazendo várias afirmações em tentativa de convencer pessoas a adotarem-a, entretanto essas afirmações tendem a ser de caráter de opinião e preferência pessoal (Altherwi, 2019), ou em casos de afirmações a respeito de segurança ou performance, difícil de provar se não em projetos maiores, tornando a verificação de tais afirmações mais difícil (Meryerovich; Rabkin, 2012). 

Dito isso, historicamente, os desenvolvedores tendem a priorizar a expressividade e a velocidade de desenvolvimento das linguagens que pretendem adotar (Meryerovich; Rabkin, 2013), portanto, linguagens que prometem simplicidade e produtividade (como o Go) muitas vezes têm mais apelo inicial. Enquanto um contra mencionado a respeito da adoção do Rust é a curva de aprendizado(Fulton et al, 2021): para verificar suas características ‘inovadoras’ é necessário primeiro um processo de aprendizado e familiarização muitas vezes lento (Farshidi; Jansen; Deldar, 2021).

Ao observar o número de repositórios no GitHub, nota-se que Go possui muito mais projetos que Rust, o que pode indicar maior adoção, popularidade e aceitação, mesmo quando pesquisas apontam Rust como a linguagem mais admirada.



Trabalhos relacionados
Diversos estudos têm investigado como linguagens de programação são utilizadas na prática e quais fatores influenciam sua adoção. Um dos trabalhos mais abrangentes nesse contexto é o de Altherwi em An Empirical Study of Programming Languages in Open-Source  Software Projects based on Mining Software Repositories, que analisa um grande conjunto de projetos hospedados no GitHub para compreender padrões de uso, qualidade e popularidade das linguagens. O estudo identifica diferenças relevantes entre linguagens em métricas como tamanho de código, atividade de desenvolvimento e produtividade, além de demonstrar como características da linguagem podem influenciar atributos do software, ainda que de maneira limitada. Uma conclusão central do trabalho é que os efeitos da linguagem existem, mas são sutis em comparação a fatores como tamanho do projeto e número de contribuidores. Esses achados dialogam diretamente com a discussão sobre Rust e Go, especialmente no que diz respeito ao impacto real de escolhas linguísticas em projetos de larga escala.
Complementarmente, Pang, Anslow e Noble, em What Programming Languages Do Developers Use? A Theory of Static vs Dynamic Language Choice, investigam a perspectiva dos desenvolvedores para compreender como ocorre a seleção de linguagens em ambientes profissionais. Utilizando entrevistas e métodos qualitativos, os autores mostram que fatores sociotécnicos desempenham papel central, incluindo experiência pessoal, familiaridade prévia, disponibilidade de bibliotecas, influência de equipes e até preferências herdadas de projetos anteriores. O estudo revela ainda que muitos desenvolvedores utilizam uma linguagem não porque a preferem, mas porque ela já está consolidada no ecossistema da organização, reforçando a importância do código legado e da infraestrutura existente no processo de adoção. Esses resultados são particularmente relevantes para compreender por que linguagens mais novas, como Rust, enfrentam barreiras de entrada maiores mesmo oferecendo vantagens técnicas significativas.
Empirical Analysis of Programming Language Adoption, de Meyerovich e Rabkin, aprofunda a discussão ao investigar como características sociológicas e organizacionais influenciam a difusão de linguagens de programação. Os autores demonstram que a adoção depende menos de atributos técnicos isolados e mais de fatores como tamanho das comunidades, suporte de ferramentas, confiança institucional e legitimidade percebida. O estudo argumenta ainda que promessas iniciais feitas por projetistas e usuários entusiastas frequentemente são baseadas em percepções subjetivas, o que dificulta a validação dessas alegações em estágios iniciais da linguagem . Esses resultados reforçam questões discutidas na fundamentação teórica, como o ceticismo que linguagens novas enfrentam e o alto custo de avaliação associado a tecnologias emergentes.
Em conjunto, esses trabalhos sustentam que a adoção de linguagens de programação é um processo complexo, multicausal e profundamente influenciado por fatores sociais, técnicos e econômicos.
Apesar da existência das pesquisas sobre adoção de linguagens de programação, observa-se uma lacuna na literatura em relação a ausência de estudos comparativos diretos entre Rust e Go, duas linguagens que, embora tenham sido lançadas em períodos próximos e compartilhem objetivos semelhantes relacionados a desempenho e segurança, são analisadas majoritariamente de forma isolada ou comparadas com outras linguagens. Essa comparação é relevante porque Rust e Go pertencem à mesma geração de linguagens modernas, surgidas como alternativas contemporâneas ao C e ao C++, e compreender suas diferenças de adoção pode esclarecer de forma mais ampla como fatores técnicos e sociotécnicos moldam a popularidade de tecnologias emergentes. Dessa forma, ao investigar paralelamente Rust e Go, este trabalho busca contribuir para essa lacuna, analisando como fatores técnicos e sociotécnicos influenciam a percepção, popularidade e adoção dessas duas linguagens.

Análise Literária( Quais fatores técnicos e sociotécnicos são mais citados na literatura e em indicadores públicos para explicar a adoção de Go e Rust?)
A literatura especializada identifica diversos fatores técnicos e sociotécnicos associados à adoção das linguagens de programação Rust e Go. De modo geral, essas linguagens são apresentadas como alternativas às limitações observadas em linguagens mais tradicionais, oferecendo avanços em aspectos como segurança, concorrência e produtividade no desenvolvimento de software. Além disso, destaca-se a influência do suporte institucional de grandes empresas de tecnologia no processo de difusão dessas linguagens. Entre os fatores técnicos mais frequentemente mencionados encontram-se a gestão de memória e segurança, o suporte à concorrência e escalabilidade, o desempenho e a velocidade de compilação.

No caso de Rust, o fator técnico mais frequentemente destacado na literatura é a segurança de memória sem a utilização de coletor de lixo (garbage collector). A linguagem é frequentemente apontada como a primeira a oferecer garantias de segurança de memória com amplo suporte industrial, conciliando controle direto de recursos com mecanismos que previnem erros comuns de programação. O sistema de tipos e o modelo de propriedade (ownership) impedem diversas formas de violações de segurança de memória, incluindo data races (acessos não sincronizados à memória compartilhada), contribuindo para o desenvolvimento de software mais seguro e confiável (Jung et al., 2021).

Em relação à linguagem Go, os estudos indicam que sua adoção inicial esteve associada principalmente ao suporte nativo à concorrência e ao paralelismo, bem como à simplicidade do processo de compilação e implantação. Entretanto, seu crescimento sustentado é atribuído a um conjunto mais amplo de fatores, particularmente ao foco no desenvolvimento de software em larga escala. Diferentemente de linguagens que priorizam inovações em aspectos sintáticos, semânticos ou de tipagem, Go foi concebida com ênfase no ecossistema de desenvolvimento como um todo, incluindo ferramentas e práticas voltadas à produtividade e à manutenção de grandes bases de código (Cox et al., 2022).

O desempenho também constitui um fator técnico relevante para ambas as linguagens. No caso de Rust, busca-se oferecer abstrações de alto nível sem penalidades significativas de desempenho. A ausência de coletor de lixo contribui para menor consumo de memória e processamento, além de maior previsibilidade no tempo de execução (Jung et al., 2021). Em Go, embora a linguagem utilize coletor de lixo, este foi projetado para apresentar baixa latência e comportamento previsível, reduzindo o impacto de pausas na execução e favorecendo aplicações distribuídas e serviços de longa duração (Meyerson, 2014).

No que se refere aos fatores sociotécnicos, a literatura aponta o apoio corporativo e a existência de aplicações reais em larga escala como elementos relevantes para a adoção de ambas as linguagens. Go está fortemente associada ao Google, tendo sido desenvolvida com o objetivo de solucionar problemas internos relacionados à manutenção de grandes bases de código e ao trabalho colaborativo entre numerosos desenvolvedores, o que contribuiu para sua credibilidade inicial (Cox et al., 2022). Rust, originalmente desenvolvida pela Mozilla, consolidou sua visibilidade a partir da adoção por grandes empresas de tecnologia, como Facebook e Microsoft. A Microsoft, por exemplo, declarou publicamente a utilização da linguagem como estratégia para reduzir vulnerabilidades de segurança em seus sistemas (Jung et al., 2021).

Outros fatores sociotécnicos associados à adoção de Rust incluem a disponibilidade de bibliotecas open source, identificada como elemento influente na escolha de linguagens de programação (Meyerovich; Rabkin, 2013). Esse aspecto é evidenciado pela existência de repositórios como o crates.io, que reúne um grande número de pacotes reutilizáveis. Destacam-se ainda a existência de uma comunidade ativa, a documentação abrangente e as mensagens de erro detalhadas, características frequentemente citadas como elementos que contribuem para mitigar as dificuldades associadas à curva de aprendizado da linguagem (Fulton et al., 2021).

No caso de Go, a simplicidade sintática e a facilidade de aprendizado são apontadas como fatores relevantes para sua adoção. Ferramentas padronizadas, como o gofmt, contribuem para a uniformização do estilo de código, promovendo maior legibilidade e facilitando a colaboração entre desenvolvedores e a manutenção de projetos (Meyerson, 2014).

 

Fontes
Software Developers Statistics 2024 - State of Developer Ecosystem Report. Disponível em: <https://www.jetbrains.com/lp/devecosystem-2024>.

Tools and Trends - The State of Developer Ecosystem in 2025. Disponível em: <https://devecosystem-2025.jetbrains.com/tools-and-trends>.

Technology | 2024 Stack Overflow Developer Survey. Disponível em: <https://survey.stackoverflow.co/2024/technology#admired-and-desired>

Technology | 2025 Stack Overflow Developer Survey. Disponível em: <https://survey.stackoverflow.co/2025/technology#most-popular-technologies-platform>. Acesso em: 2 nov. 2025.

Case Studies - The Go Programming Language. Disponível em: <https://go.dev/solutions/case-studies>.

Rust Programming Language. Disponível em: <https://rust-lang.org>.

FARSHIDI, S.; JANSEN, S.; DELDAR, M. A decision model for programming language ecosystem selection: Seven industry case studies. Information and Software Technology, v. 139, p. 106640, nov. 2021.

O’CONNOR, R. V. A study of computer programming language adoption for information systems development projects. International Journal of Technology Policy and Management, v. 3, n. 3/4, p. 343–343, 1 jan. 2003.

MEYEROVICH, L. A.; RABKIN, A. S. Empirical analysis of programming language adoption. Proceedings of the 2013 ACM SIGPLAN international conference on Object oriented programming systems languages & applications, 29 out. 2013.

PANG, A.; ANSLOW, C.; NOBLE, J. What Programming Languages Do Developers Use? A Theory of Static vs Dynamic Language Choice. 2018 IEEE Symposium on Visual Languages and Human-Centric Computing (VL/HCC), out. 2018.

ARUNDEL, J. For the Love of Go. 2023 Edition ed. [s.l: s.n.].

MUNA ALTHERWI. An empirical study of programming language effect on open source software development. p. 49–51, 11 out. 2019.

BLANDY, J.; ORENDORFF, J.; TINDALL, L. Programming Rust, 2nd Edition. [s.l.] O’Reilly Media, Inc., 2021.

FULTON, Kelsey R.; CHAN, Anna; VOTIPKA, Daniel; HICKS, Michael; MAZUREK, Michelle L. Benefits and drawbacks of adopting a secure programming language: Rust as a case study. In: SEVENTEENTH SYMPOSIUM ON USABLE PRIVACY AND SECURITY (SOUPS 2021), 2021, Boston. Proceedings [...]. Berkeley, CA: USENIX Association, 2021. p. 597–616. Disponível em: https://www.usenix.org/conference/soups2021/presentation/fulton
. Acesso em: 8 nov. 2025.

MEYERSON, J. The Go Programming Language. IEEE Software, v. 31, n. 5, p. 104–104, set. 2014.

NERLOVE, M. Programming languages: A short history for economists. Journal of Economic and Social Measurement, v. 29, n. 1-3, p. 189–203, 20 jul. 2004.

KUMAR, Rajinder; KAUR, Charnajeet; SINGH, Sonwinder. The evolution of programming languages: from assembly language to modern high-level languages. International Journal of Creative Research and Management (IJCRM), v. 4, n. 5, p. 471–477, out. 2025

MICHAELSON, Greg. Programming paradigms and computational thinking. Edinburgh: Heriot-Watt University, School of Mathematical and Computer Sciences, 2018.

FARXODJON O‘G‘LI, Abduraxmonov Samandar. Programming languages and concepts about them. Young Scientist Research Journal of Karakalpakstan, v. 1, n. 4, p. 253, out. 2024.

WINKFIELD, Leah; HU, Yen-Hung; HOPPA, Mary Ann. A study of the evolution of secure software development architectures. Journal of the Colloquium for Information Systems Security Education, v. 6, n. 1, p. 19–19, 2018.

OLEG ZHULKOVSKYI et al. COMPARATIVE ANALYSIS OF COMPUTATIONAL PERFORMANCE OF MODERN PROGRAMMING LANGUAGES. Computer systems and information technologies, n. 2, p. 104–111, 2025.

VIITANEN, Tuukka. A comparative analysis of modern programming languages in REST API development. 2025. 77 f. Bachelor’s Thesis (Degree Programme in ICT Engineering – Software Engineering) – Tampere University of Applied Sciences, Tampere, 2025.

JUNG, R. et al. Safe systems programming in Rust. Communications of the ACM, v. 64, n. 4, p. 144–152, abr. 2021.

BLANDY, Jim; ORENDORFF, Jason; TINDALL, Leonora F. S. Programming Rust. 2. ed. Sebastopol: O’Reilly Media, 2021.

BUGDEN, W.; AYMAN ALAHMAR. Rust: The Programming Language for Safety and Performance. ResearchGate, 11 jun. 2022.

crates.io: Rust Package Registry. Disponível em: <https://crates.io>

MEYEROVICH, Leo A.; RABKIN, Ariel S. Socio-PLT: principles for programming language adoption. In: ACM INTERNATIONAL SYMPOSIUM ON NEW IDEAS, NEW PARADIGMS, AND REFLECTIONS ON PROGRAMMING AND SOFTWARE – ONWARD!, 2012. Proceedings [...]. New York: ACM, 2012. p. 39-54. 

COX, Russ; GRIESEMER, Robert; PIKE, Rob; TAYLOR, Ian Lance; THOMPSON, Ken. The Go programming language and environment. Communications of the ACM, New York, v. 65, n. 5, p. 70–78, maio 2022. DOI: https://doi.org/10.1145/3488716
