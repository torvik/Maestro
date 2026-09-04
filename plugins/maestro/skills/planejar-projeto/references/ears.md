# EARS — critérios de aceite que viram teste

Notação criada na indústria aeroespacial e hoje o padrão para critério de aceite legível por humano e por modelo. Cinco padrões cobrem quase tudo.

## 1. Ubíquo — vale sempre
```
O SISTEMA DEVE <comportamento>.
```
> O SISTEMA DEVE registrar toda chamada de modelo com custo e contagem de tokens.

## 2. Dirigido por evento — QUANDO
```
QUANDO <gatilho> O SISTEMA DEVE <comportamento>.
```
> QUANDO o usuário envia uma imagem acima de 8 MB O SISTEMA DEVE recusar e responder com o limite.

## 3. Dirigido por estado — ENQUANTO
```
ENQUANTO <estado> O SISTEMA DEVE <comportamento>.
```
> ENQUANTO houver um bloco em execução O SISTEMA DEVE recusar o despacho de um segundo bloco.

## 4. Condicional indesejado — SE / ENTÃO
```
SE <condição indesejada> ENTÃO O SISTEMA DEVE <resposta>.
```
> SE a chamada ao modelo falhar três vezes ENTÃO O SISTEMA DEVE marcar o bloco como bloqueado e parar.

## 5. Opcional — ONDE
```
ONDE <recurso presente> O SISTEMA DEVE <comportamento>.
```
> ONDE houver credencial configurada O SISTEMA DEVE validar o link antes de gravar.

## Combinações
Padrões se aninham para casos complexos:
```
QUANDO <gatilho> SE <condição> ENTÃO O SISTEMA DEVE <comportamento>.
```

## Regras de escrita
1. **Um DEVE por critério.** Dois comportamentos numa frase viram dois critérios.
2. **Sujeito explícito.** "O SISTEMA", não "ele" nem voz passiva.
3. **Número em vez de adjetivo.** "em até 2 segundos", não "rápido". "no máximo 3 frases", não "curto".
4. **Comportamento observável.** Se você não consegue escrever a asserção do teste, o critério ainda está vago.
5. **Sem conjunção escondida.** "e/ou" quase sempre esconde dois critérios.

## Do critério ao teste
Cada critério EARS vira um caso de teste com o mesmo nome. É essa correspondência que permite ao revisor conferir item por item — e ao executor saber quando terminou.

| EARS | Teste |
|---|---|
| QUANDO … O SISTEMA DEVE … | caso de caminho feliz |
| SE … ENTÃO O SISTEMA DEVE … | caso de erro / borda |
| ENQUANTO … | caso de estado / concorrência |

## Antipadrões
| Ruim | Por quê | Bom |
|---|---|---|
| "O sistema deve ser rápido" | Não mensurável | "O SISTEMA DEVE responder em até 2 s no percentil 95" |
| "Tratar erros adequadamente" | "Adequadamente" não é verificável | "SE o banco estiver indisponível ENTÃO O SISTEMA DEVE retornar 503 e registrar o erro" |
| "Deve funcionar bem no celular" | Sem critério | "O SISTEMA DEVE renderizar sem rolagem horizontal a partir de 360 px" |
