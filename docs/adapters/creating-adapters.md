# Como criar um adapter

Um adapter conecta um harness (Claude Code, Codex, um CLI qualquer) aos dois
contratos do Maestro: `UCP` (o que o executor recebe) e `UEP` (o que o
executor emite). Ver `docs/architecture/protocol.md` para os contratos em si
e `plano/specs/F14-02-adapter-sdk.md` para a spec completa deste SDK.

## O mínimo necessário: um manifest

Todo adapter precisa de um `adapter.manifest.json`:

```json
{
  "name": "meu-adapter",
  "version": "1.0.0",
  "harness": "meu-harness",
  "supported_events": [
    "block_started", "file_read", "file_written",
    "test_run", "block_completed", "block_failed"
  ],
  "capabilities": {
    "streaming_events": false,
    "structured_output": false,
    "shell_execution": true
  }
}
```

| Campo | Obrigatório | Regra |
|-------|-------------|-------|
| `name` | sim | identificador único, string não vazia |
| `version` | sim | string não vazia (ex. semver) |
| `harness` | sim | nome do harness subjacente |
| `supported_events` | sim | lista não vazia; cada item deve ser um dos 6 eventos do UEP (`packages.core.protocol.EventType`) |
| `capabilities` | sim | objeto; pode ser vazio; feature flags livres |
| `adapter_api_version` | não | default `1` |
| `description` | não | default `""` |

Um manifest com campo obrigatório ausente, `supported_events` vazio, ou um
evento fora dos 6 conhecidos falha a validação com `ValidationError`.

Se o seu adapter não precisa de lógica Python (o harness já sabe falar com o
Maestro via os scripts de lifecycle — `maestro_run.py start/test/finish`),
**o manifest sozinho já é suficiente**. É o caso de `claude-code` e `codex`
hoje: veja `integrations/claude-code/adapter.manifest.json` e
`integrations/codex/adapter.manifest.json`.

## Validando o manifest

```python
from packages.core.protocol.conformance import AdapterManifest

manifest = AdapterManifest.from_file("integrations/meu-adapter/adapter.manifest.json")
```

Levanta `ValidationError` (subclasse de `ValueError`) se algo estiver errado.

## Registrando o adapter

```python
from packages.core.protocol.conformance import AdapterRegistry

registry = AdapterRegistry()
registry.register("integrations/meu-adapter/adapter.manifest.json")
assert registry.is_registered("meu-adapter")
```

`register()` valida **antes** de ativar: se o manifest for inválido, nada é
gravado no registro — não existe estado parcial. Você também pode registrar
com um objeto adapter Python associado: `registry.register(manifest, adapter)`.

## Rodando a conformance suite

Qualquer adapter — com ou sem objeto Python — pode rodar a suite contra o
próprio manifest:

```python
from packages.core.protocol.conformance import ConformanceSuite

suite = ConformanceSuite("integrations/meu-adapter/adapter.manifest.json")
suite.run()
assert suite.ok, suite.failures()
```

Os checks de manifest (sempre rodam):

- `manifest_parses` — o arquivo/dict parseia e valida.
- `supported_events_valid` — não vazio, todo item é um `EventType` conhecido.
- `capabilities_is_object` — `capabilities` é um objeto.

## Adicionando um objeto Python (opcional)

Se o seu adapter também expõe uma classe Python (como `GenericCLIAdapter`),
implemente dois métodos para ganhar cobertura de runtime na suite:

```python
class MeuAdapter:
    manifest: AdapterManifest

    def build_invocation(self, ucp: UCP) -> list[str]:
        """Traduz um UCP em um comando executável (argv). Retorna lista
        não vazia; nunca lança para um UCP válido."""
        ...

    def parse_event_line(self, line: str) -> UCPEvent | None:
        """Tenta interpretar uma linha de saída do harness como UCPEvent.
        Retorna None quando a linha não é reconhecível -- nunca lança."""
        ...
```

Não existe uma classe base obrigatória: Python usa duck typing, qualquer
objeto com esses dois métodos passa nos checks `adapter_builds_invocation` e
`adapter_parses_event_line` quando você passa o objeto para
`ConformanceSuite(manifest, adapter)`.

## Usando o Generic CLI adapter

Para uma ferramenta de linha de comando sem adapter dedicado, use
`GenericCLIAdapter` em vez de escrever uma classe do zero:

```python
from packages.core.protocol.conformance import GenericCLIAdapter, ConformanceSuite

adapter = GenericCLIAdapter(name="minha-ferramenta", command=["minha-ferramenta", "run"])

suite = ConformanceSuite(adapter.manifest, adapter)
suite.run()
assert suite.ok
```

`GenericCLIAdapter.build_invocation(ucp)` completa o comando base com
`ucp.block_spec.test_command` quando presente.
`GenericCLIAdapter.parse_event_line(line)` tenta interpretar cada linha de
saída como JSON de um `UCPEvent`, e retorna `None` (sem lançar) quando a
linha não é reconhecível. Note que `GenericCLIAdapter` **não** executa o
subprocess por você — isso é responsabilidade de quem invoca o adapter, fora
do escopo deste SDK (ver `plano/specs/F14-02-adapter-sdk.md` seção 3).

## Checklist para um novo adapter

1. Escreva `adapter.manifest.json` com os 5 campos obrigatórios.
2. Rode `AdapterManifest.from_file(...)` e confirme que não levanta.
3. Rode `ConformanceSuite(manifest).run()` e confirme `suite.ok`.
4. Se houver objeto Python, implemente `build_invocation` e
   `parse_event_line`, passe-o para a suite e confirme `suite.ok` de novo.
5. Registre com `AdapterRegistry().register(manifest, adapter)`.
