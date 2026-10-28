<div align="center">

# 📜 LIVRO DE REGRAS

### Chronicles of the Abyss — Jogo de Cartas Estratégico

**Versão de referência para desenvolvimento · 28/10/2026**

[⬅️ Voltar à página principal](./README.md) · [⚔️ Combate](#7-sistema-de-combate) · [🧙 Habilidades](#12-habilidades-e-efeitos)

</div>

> [!IMPORTANT]
> Este documento consolida as regras discutidas para o projeto. Alguns detalhes técnicos ainda precisam de decisão e estão identificados em **Pontos pendentes**. O título do jogo é provisório.

## 1. Objetivo e condição de vitória

- Partida disputada entre **dois jogadores**.
- Cada jogador inicia com **40 pontos de vida**.
- A principal condição de vitória é reduzir a vida do oponente a **0**.
- A partida termina quando essa condição é atingida.
- Não há sistema de empate formalmente definido.

## 2. Baralho e cartas de prêmio

- Cada jogador prepara **44 cartas**: **40** para o baralho principal e **4** cartas de prêmio separadas.
- Uma mesma carta pode ter até **4 cópias**; não foi estabelecida uma restrição adicional por raridade.
- As quatro cartas de prêmio são escolhidas na construção do baralho e permanecem ocultas ao adversário até serem reveladas ou utilizadas.
- Os prêmios não entram no campo automaticamente; precisam ser jogados conforme seu custo e tipo.

## 3. Preparação da partida

1. Ambos os jogadores iniciam com **40 de vida** e **2 pontos de surgimento**.
2. Cada um compra **5 cartas** do próprio baralho.
3. Uma moeda determina quem age primeiro nas fases de Campo e Preparação.
4. Realiza-se um **mulligan**: cada carta da mão inicial pode ser trocada uma única vez. As escolhidas retornam ao baralho, que é embaralhado antes da compra das substitutas.
5. Começa a primeira rodada.

## 4. Tabuleiro e posicionamento

- Cada jogador controla **5 colunas**.
- Cada coluna tem uma posição de **frente** e outra de **retaguarda**, totalizando **10 posições de criaturas por jogador**.
- Colunas adversárias são alinhadas para resolução das batalhas.
- A **frente** protege a **retaguarda** contra ataques convencionais.
- Uma criatura na retaguarda **também pode atacar**, mesmo enquanto a frente estiver ocupada.
- Sem criatura na frente, a retaguarda fica exposta aos ataques convencionais daquela coluna.
- Criaturas não se deslocam livremente; movimentos precisam de habilidades ou outros efeitos que os autorizem.

## 5. As cinco fases de cada rodada

| Fase | Responsável | Resumo |
|---|---|---|
| **1. Campo** | Primeiro jogador | Ações e habilidades permitidas na fase de Campo. |
| **2. Campo** | Segundo jogador | Ações equivalentes do segundo jogador. |
| **3. Preparação** | Primeiro jogador | Jogar criaturas, feitiços, itens e utilizar recursos e efeitos válidos. |
| **4. Preparação** | Segundo jogador | Ações equivalentes do segundo jogador. |
| **5. Batalhas** | Ambos | Resolver combates das cinco colunas, em ordem da esquerda para a direita. |

Ao final da fase de Batalhas, os jogadores recebem surgimento, realizam a compra normal de cartas e os contadores do cemitério são atualizados. Se ninguém venceu, começa a próxima rodada.

## 6. Surgimento

- Surgimento é o recurso usado para pagar **criaturas, feitiços, itens e habilidades com custo**.
- Cada jogador inicia com **2 pontos**.
- Surgimento **não utilizado é acumulado**, sem teto máximo estabelecido.
- Após a **primeira** fase de Batalhas concluída, cada jogador recebe **+1**; depois da segunda, **+2**; da terceira, **+3**; e assim sucessivamente.
- Cada ganho depende do número de batalhas concluídas, e não do saldo atual.
- Ações que exigem custo só podem ser realizadas quando existe surgimento suficiente, salvo efeito explícito em contrário.

**Exemplo, sem gastos:** 2 iniciais → 3 após a primeira batalha → 5 após a segunda → 8 após a terceira.

## 7. Sistema de combate

### 7.1. Ordem e alvos

- A batalha acontece na **quinta fase**.
- Resolvem-se as colunas **da esquerda para a direita**.
- Ataques convencionais visam primeiro a criatura da **frente** da coluna adversária.
- Se a frente estiver desocupada, a criatura da **retaguarda** pode ser atacada.
- Se a coluna adversária estiver totalmente vazia, as criaturas aptas podem causar **dano direto ao jogador**.
- Habilidades específicas podem alterar alvo, alcance ou prioridade conforme seu texto.

### 7.2. Simultaneidade e dano

- Os ataques de uma mesma resolução são **simultâneos**.
- Uma criatura que recebe dano letal ainda executa o ataque simultâneo já determinado.
- Depois da aplicação dos danos, criaturas com vida igual ou inferior a zero são eliminadas.
- **Dano excedente** não passa automaticamente para outra criatura ou para o jogador.
- O **dano restante permanece marcado** nas criaturas sobreviventes entre as rodadas.
- Recuperação de vida exige efeitos de cura ou restauração, sem ultrapassar o máximo da criatura, salvo indicação específica.
- O atributo de ataque não pode ser reduzido abaixo de **0**.

### 7.3. Dano direto e vitória

- Quando não houver defensor válido na coluna, cada criatura apta causa seu próprio dano direto à vida do adversário.
- Habilidades também podem causar dano direto em condições específicas.
- Após cada efeito relevante, verifica-se a vida dos jogadores e os marcos de prêmio.

## 8. Cartas de prêmio

| Dano acumulado causado ao adversário | Recompensa |
|---:|---|
| **8** | 1º prêmio |
| **16** | 2º prêmio |
| **24** | 3º prêmio |
| **32** | 4º prêmio |

- O jogador escolhe qual carta de prêmio ainda disponível deseja receber.
- O prêmio escolhido vai **diretamente para a mão**, não para o campo.
- Os custos normais continuam válidos.
- Se um único ataque ultrapassar múltiplos marcos, os prêmios correspondentes são liberados.
- Cada prêmio é obtido apenas uma vez; **curar o adversário não desfaz marcos já alcançados**.
- O máximo é de **quatro prêmios por partida**.

## 9. Compra de cartas e baralho vazio

- A mão inicial contém **5 cartas**.
- Cada jogador compra **1 carta por rodada completa**, após a fase de Batalhas.
- Efeitos podem conceder compras adicionais.
- Não existe limite máximo geral de cartas na mão definido.
- Cartas de prêmio não fazem parte do baralho principal nem da compra comum.
- Esgotar o baralho **não causa derrota automática**.
- Foi discutida uma **compra especial de até três cartas** em situação de esgotamento; seu gatilho e a ordem exata com a reciclagem precisam ser detalhados antes da implementação definitiva.

## 10. Cemitério e reciclagem

- Criaturas eliminadas, feitiços resolvidos e itens destruídos podem ir ao **cemitério do proprietário**.
- Cartas no cemitério retornam automaticamente ao baralho após **duas rodadas completas / duas fases de Batalhas concluídas**, conforme a contagem definida para o jogo.
- A implementação deve registrar quando cada carta entrou no cemitério e evitar retorno antecipado.
- Ao retornar ao baralho, uma criatura recupera seu estado inicial: vida original e sem modificadores temporários anteriores.
- O retorno ao baralho **não é uma invocação em campo**.
- Efeitos específicos podem **recuperar ou ressuscitar** cartas antes da reciclagem, respeitando o destino indicado pelo texto da carta.

## 11. Tipos de cartas

### 🐉 Criaturas

- Têm **custo de surgimento, ataque, vida** e, quando aplicável, habilidades.
- Ocupam frente ou retaguarda e podem pertencer a tribos ou famílias (ex.: Esqueleto, Zumbi, Vampiro, Goblin, Planta, Humano, Lobo).
- Podem portar um item e vão ao cemitério quando eliminadas.

### 🔮 Feitiços

- Pagam custo de surgimento e resolvem seu efeito conforme o texto.
- São usados nas fases permitidas pela carta ou pelas regras gerais.
- Após a resolução, seguem para o cemitério, salvo exceção expressa.

### 🛡️ Itens

- São equipáveis em criaturas, com limite de **um item por criatura**.
- Concedem atributos e/ou efeitos enquanto suas condições forem atendidas.
- Podem ser equipados nas fases de Campo ou Preparação, conforme a regra discutida.
- Se a criatura equipada morrer, o item segue para o cemitério.

### 🌍 Terrenos

- Afetam uma **coluna inteira**, podendo envolver criaturas de ambos os jogadores conforme a descrição.
- Não ocupam os espaços de frente ou retaguarda.
- São representados visualmente abaixo da coluna.

## 12. Habilidades e efeitos

### Categorias

- **Ativáveis:** acionadas pelo jogador sob condições específicas; em regra, cada habilidade ativável pode ser usada **uma vez por rodada**, salvo texto em contrário.
- **Passivas:** aplicam efeitos continuamente enquanto sua condição estiver satisfeita.
- **Ao entrar:** disparam quando a criatura entra em campo, inclusive após ressurreição que a coloque novamente ali.
- **Ao morrer:** disparam quando a criatura é eliminada.
- **Ao sobreviver:** dependem de resistir até o momento definido na carta.

### Custos, resposta e efeitos

- Habilidades só podem ser usadas com **condições e alvos válidos**.
- Se houver custo descrito, deve ser pago; sem custo explícito, não se gasta surgimento.
- Durante o combate, podem existir **respostas com prioridade alternada** entre jogadores, conforme as janelas de ativação que serão detalhadas na implementação.
- Efeitos idênticos podem **se acumular**, sem limite geral estabelecido.
- Efeitos positivos e negativos seguem sua duração e podem ser removidos por cartas que expressem restauração.
- Resultados aleatórios, inclusive **cara ou coroa**, precisam ser sorteados pelo sistema, sem escolha manual do resultado.

## 13. Alvos, buscas e invocações por efeito

- Uma habilidade só pode selecionar os alvos descritos em seu texto.
- A criatura não pode selecionar a si mesma, a menos que a habilidade permita.
- Se o alvo deixar de ser válido antes da resolução, o efeito direcionado a ele falha, conforme a regra discutida.
- Se uma habilidade busca cartas no baralho, deve seguir o critério da busca; depois, o baralho é **embaralhado**.
- Foi discutido que uma busca sem cartas válidas resulta em **compra normal**; as exceções por carta ainda devem ser especificadas.
- Invocações geradas por habilidade não consomem surgimento extra, salvo custo descrito.
- A invocação exige **espaço válido**; sem espaço, falha.
- Uma criatura invocada diretamente em campo ativa efeitos **ao entrar**.
- A ressurreição deve indicar de onde a carta vem e para onde vai (mão, campo etc.).

## 14. Movimentação e equipamentos

- Não há deslocamento livre entre colunas ou fileiras.
- Mudanças de posição exigem **efeitos que autorizem o movimento**.
- Uma posição ocupada não pode receber outra criatura sem efeito que preveja troca ou exceção.
- O limite de equipamento é **um item por criatura**.

## 15. Fluxo resumido da fase de Batalhas

1. Iniciar a quinta fase.
2. Selecionar a coluna mais à esquerda ainda não resolvida.
3. Identificar criaturas, alvos e efeitos válidos.
4. Abrir as oportunidades de habilidade aplicáveis.
5. Determinar ataques simultâneos.
6. Aplicar dano e efeitos pertinentes.
7. Resolver mortes e seus efeitos.
8. Enviar cartas eliminadas ao cemitério.
9. Aplicar dano direto, quando houver.
10. Atualizar marcos de prêmio e verificar vitória.
11. Caso a partida continue, passar à próxima coluna.
12. Após a quinta coluna, conceder surgimento, comprar cartas e atualizar o cemitério.

## 16. Regras que NÃO devem ser alteradas sem decisão do projeto

- **40 de vida** iniciais.
- **44 cartas** por baralho: **40 principais + 4 prêmios**.
- **Até 4 cópias** de cada carta.
- **5 colunas**, cada uma com **frente e retaguarda**, para cada jogador.
- A retaguarda **pode atacar mesmo com a frente ocupada**.
- **5 fases** por rodada.
- **2 pontos de surgimento** iniciais, com progressão acumulativa e **sem teto máximo**.
- Dano de criaturas **persiste** entre rodadas.
- Combate da **esquerda para a direita**.
- Prêmios aos **8 / 16 / 24 / 32** pontos de dano acumulado.
- Reciclagem do cemitério após **duas rodadas completas**.
- Um item equipado por criatura.
- Vitória ao reduzir o adversário a **0 de vida**.

## 17. Pontos pendentes de especificação

> [!WARNING]
> **Não presumir regras que ainda não foram fechadas.** O objetivo desta seção é facilitar o trabalho de implementação e testes.

- Sequenciamento exato de ataques entre frente e retaguarda dentro de uma coluna com múltiplas criaturas.
- Janelas de resposta, prioridades e desempate na resolução de habilidades simultâneas.
- Momento preciso dos contadores de duas rodadas para cada carta enviada ao cemitério.
- Gatilho exato da compra especial de até três cartas com baralho vazio.
- Interação completa entre terrenos concorrentes e mudanças de terreno.
- Regra geral para situações em que ambos os jogadores chegam a zero na mesma resolução.
- Limitações específicas de habilidades por cartas e casos de exceção.

---

<div align="center">

**📜 Regras para orientar a implementação e manter o jogo consistente.**

[⬅️ Voltar ao README principal](./README.md)

</div>
