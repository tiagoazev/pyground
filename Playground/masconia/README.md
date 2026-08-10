# Masconia: Chronicles of the Mysterious Smoke

Roguelike tático top-down em grid, com combate por turnos estilo D&D (d20 + modificadores),
progressão dupla (intra-run + meta-progressão com "Alma do Dragão"), e geração procedural
de masmorras em 3 biomas temáticos.

## Arquitetura

```
masconia/
├── main.py                 # Entry point
├── requirements.txt        # Dependências
│
├── ecs/                    # Núcleo ECS (Entity-Component-System)
│   ├── entity.py           # Entidade (container de ID + componentes + tags)
│   ├── world.py            # World (gerencia entidades, systems, eventos, queries)
│   └── __init__.py
│
├── components/             # Dados puros (zero lógica)
│   ├── position.py         # Posição no grid (x, y, facing)
│   ├── renderable.py       # Sprite, cor, animação, z-index
│   ├── stats.py            # Atributos D&D, HP/MP/XP, CA, nível
│   ├── inventory.py        # Itens, equipamentos, ouro, Alma do Dragão
│   ├── fighter.py          # Ataques, resistências, condições, ações/turno
│   ├── ai.py               # Comportamento, fases de boss, cooldowns
│   └── __init__.py
│
├── systems/                # Lógica que opera sobre componentes
│   ├── render_system.py    # Renderização, câmera, UI, animações
│   ├── movement_system.py  # Movimento, colisão, pathfinding A*
│   ├── ai_system.py        # IA tática (percepção, decisão, execução)
│   └── __init__.py
│
├── dungeon/                # Geração procedural
│   ├── generator.py        # Algoritmo de salas+corredores, biomas, seeds
│   └── __init__.py
│
├── combat/                 # Sistema de combate D&D
│   ├── system.py           # Rolagens d20, críticos, dano, resistências, XP/loot
│   └── __init__.py
│
├── entities/               # Factories de entidades
│   ├── player.py           # Cria jogador baseado em classe (JSON)
│   ├── enemy.py            # Cria inimigos por bioma (JSON)
│   └── __init__.py
│
├── screens/                # Máquina de estados do jogo
│   ├── game_state.py       # Todos os estados (menu, combate, inventário, etc.)
│   └── __init__.py
│
├── data/                   # Dados externos (balanceáveis sem código)
│   ├── classes.json        # 4 classes iniciais + stats + habilidades + equipamento
│   ├── enemies.json        # Inimigos por bioma + IA + resistências + fases de boss
│   ├── items.json          # Armas, armaduras, consumíveis, relíquias
│   └── biomes.json         # Configurações de geração por bioma
│
├── config/                 # Configurações do jogo
│   ├── settings.py         # Constantes de gameplay, resolução, cores, paths
│   └── __init__.py
│
├── utils/                  # Utilitários
│   ├── constants.py        # Enums (GameState, DamageType, TileType, etc.)
│   ├── dice.py             # Motor de rolagem D&D (d20, vantagem, críticos)
│   └── __init__.py
│
└── assets/                 # Arte (placeholder — sprites em pixel art 32x32)
    ├── sprites/
    ├── tilesets/
    └── fonts/
```

## Decisões de Design

### 1. ECS (Entity-Component-System)
Em vez de herança profunda (`Player extends Entity extends GameObject`), usamos **composição**:
- **Entity** = ID + conjunto de componentes + tags
- **Component** = dados puros (ex: `Position(x=5, y=3)`)
- **System** = lógica que processa entidades com componentes específicos

**Benefícios:**
- Um inimigo pode ter `Flying` + `Poisonous` sem criar 50 subclasses.
- Adicionar um buff temporário = adicionar um componente `Buff` à entidade.
- Systems são cache-friendly (iteram arrays homogêneos).

### 2. Dados Externos (JSON)
Todas as definições de classes, inimigos, itens e biomas estão em arquivos JSON.

**Benefícios:**
- Balanceamento sem recompilar.
- Designers podem ajustar números sem tocar em código.
- Facilita modding pela comunidade.

### 3. Seed Compartilhável
A geração de masmorra usa `random.Random(seed)` controlável.

**Benefícios:**
- Daily Challenge: todos os jogadores recebem a mesma seed (derivada da data).
- Speedruns: seed fixa permite competição justa.
- Debug: reproduzir bugs com a mesma seed.

### 4. Sistema de Dados D&D
Módulo `utils/dice.py` implementa rolagens d20 com vantagem/desvantagem,
críticos naturais (20), fumbles (1), e modificadores de atributo.

**Benefícios:**
- Testabilidade: pode mockar o RNG em testes unitários.
- Consistência: todo o jogo usa o mesmo motor de rolagem.
- Extensibilidade: fácil adicionar novos tipos de dados (d100, etc.).

### 5. IA Tática com Fases de Boss
Cada inimigo tem um `AI` componente com `behavior_type`:
- `melee_aggressive`: corre até o jogador e ataca
- `hit_and_run`: ataca e recua
- `ranged`: mantém distância
- `boss_phases`: muda comportamento baseado em % de HP

**Benefícios:**
- IA centralizada em um único system.
- Fácil adicionar novos comportamentos sem mudar inimigos existentes.
- Bosses dinâmicos que evoluem durante o combate.

## Como Executar

```bash
# 1. Instale dependências
pip install -r requirements.txt

# 2. Execute
python main.py
```

## Controles

| Tecla | Ação |
|-------|------|
| WASD / Setas | Movimento |
| Espaço | Esperar / Pular turno |
| I | Inventário |
| ESC | Voltar / Fechar |
| F1 | Debug info |

## Progressão

### Intra-run (perdido ao morrer)
- XP → Level Up → Stats aumentam
- Itens e equipamentos encontrados na masmorra
- Ouro usado na loja

### Meta-progressão (persistente)
- **Alma do Dragão**: moeda obtida ao derrotar bosses e mini-bosses
- Usada para desbloquear novas classes e relíquias entre runs
- Salva em `save/progress.json`

## Biomas

| Bioma | Andares | Tema | Inimigos |
|-------|---------|------|----------|
| Cripta | 1-5 | Mortos-vivos, escuridão | Esqueletos, Zumbis, Aparições |
| Cavernas de Cristal | 6-10 | Cristais brilhantes, eco | Lêsmas, Morcegos, Golems |
| Covil do Dragão | 11-15 | Lava, ouro, destruição | Kobolds, Drakes, Cultistas |

## Próximos Passos

O esqueleto está completo. As próximas partes a desenvolver são:

1. **Geração de Masmorra**: expandir algoritmo, adicionar armadilhas, salas secretas
2. **Sistema de Combate**: habilidades de classe, magias de área, condições (stun, poison)
3. **Classes de Personagem**: implementar habilidades especiais (Segundo Fôlego, Bola de Fogo, etc.)
4. **Arte**: sprites 32x32 em pixel art para cada classe/inimigo/bioma
5. **UI/UX**: inventário interativo, loja, tela de level up com escolhas
6. **Áudio**: música ambiente por bioma, efeitos sonoros de combate
7. **Save/Load**: persistência de progresso e runs em andamento
8. **Daily Challenge**: integração com seed diária e leaderboard

## Licença

MIT License — sinta-se livre para usar, modificar e distribuir.
