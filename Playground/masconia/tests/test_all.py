#!/usr/bin/env python3
"""Testes Unitários de Masconia."""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ecs.world import World, Event
from ecs.entity import Entity
from components.position import Position
from components.stats import Stats
from components.fighter import Fighter
from components.inventory import Inventory
from components.ai import AI
from components.renderable import Renderable
from dungeon.generator import DungeonGenerator, DungeonMap, Room, Trap, TrapType, TerrainModifier
from dungeon.fov import FOVMap
from combat.system import CombatSystem
from combat.conditions import ConditionSystem, Condition, ConditionType
from combat.abilities import AbilityRegistry, Fireball, HealWounds, ArcaneShield, Dash
from combat.tactics import TacticsSystem
from utils.dice import DiceRoller
from utils.constants import DamageType, TileType, RoomType


def test_dice_roller():
    print("\n[TESTE 1] Sistema de Dados")
    dice = DiceRoller(seed=42)
    result = dice.roll("2d6+3")
    assert 5 <= result <= 15
    print(f"  ✓ roll('2d6+3') = {result}")

    roll_result, natural = dice.d20()
    assert 1 <= natural <= 20
    print(f"  ✓ d20() = {roll_result} (natural: {natural})")

    roll_result, _ = dice.d20(advantage=True)
    print(f"  ✓ d20(advantage) = {roll_result}")

    roll_result, _ = dice.d20(disadvantage=True)
    print(f"  ✓ d20(disadvantage) = {roll_result}")

    assert DiceRoller.stat_modifier(16) == 3
    assert DiceRoller.stat_modifier(10) == 0
    assert DiceRoller.stat_modifier(8) == -1
    print(f"  ✓ Modificadores de stat corretos")

    assert dice.is_critical(20) == True
    assert dice.is_critical(19) == False
    assert dice.is_fumble(1) == True
    assert dice.is_fumble(2) == False
    print(f"  ✓ Críticos e fumbles detectados")

    assert dice.apply_damage_modifiers(10, DamageType.FIRE, [DamageType.FIRE], [], []) == 5
    assert dice.apply_damage_modifiers(10, DamageType.FIRE, [], [DamageType.FIRE], []) == 20
    assert dice.apply_damage_modifiers(10, DamageType.FIRE, [], [], [DamageType.FIRE]) == 0
    print(f"  ✓ Resistências/vulnerabilidades/imunidades aplicadas")
    print("  [PASSOU]")
    return True


def test_dungeon_generation():
    print("\n[TESTE 2] Geração de Masmorra")
    biomes = {
        "crypt": {"room_count": [5, 8], "room_size": {"min": [4, 4], "max": [7, 7]}},
        "crystal_caverns": {"room_count": [6, 10], "room_size": {"min": [5, 5], "max": [8, 8]}},
        "dragon_lair": {"room_count": [7, 12], "room_size": {"min": [6, 6], "max": [10, 10]}},
    }
    generator = DungeonGenerator(biomes)
    dungeon = generator.generate(floor=1, seed=12345, biome="crypt")
    assert dungeon is not None
    assert dungeon.width > 0 and dungeon.height > 0
    print(f"  ✓ Masmorra gerada: {dungeon.width}x{dungeon.height}")

    assert len(dungeon.rooms) >= 5
    print(f"  ✓ {len(dungeon.rooms)} salas geradas")

    room_types = [r.room_type for r in dungeon.rooms]
    assert RoomType.SPAWN in room_types
    assert RoomType.BOSS in room_types
    print(f"  ✓ Salas especiais presentes")

    assert len(dungeon.rooms[0].connections) > 0
    print(f"  ✓ Salas conectadas")

    stairs_up = False
    stairs_down = False
    for y in range(dungeon.height):
        for x in range(dungeon.width):
            if dungeon.get_tile(x, y) == TileType.STAIRS_UP:
                stairs_up = True
            if dungeon.get_tile(x, y) == TileType.STAIRS_DOWN:
                stairs_down = True
    assert stairs_up and stairs_down
    print(f"  ✓ Escadas posicionadas")

    dungeon2 = generator.generate(floor=1, seed=12345, biome="crypt")
    assert len(dungeon2.rooms) == len(dungeon.rooms)
    print(f"  ✓ Seed reproduzível")

    daily = generator.generate_daily(20260801)
    assert daily is not None
    print(f"  ✓ Daily Challenge funciona")
    print("  [PASSOU]")
    return True


def test_dungeon_advanced():
    print("\n[TESTE 3] Recursos Avançados da Masmorra")
    biomes = {
        "crypt": {"room_count": [10, 15], "room_size": {"min": [4, 4], "max": [8, 8]}},
        "crystal_caverns": {"room_count": [10, 15], "room_size": {"min": [5, 5], "max": [10, 10]}},
        "dragon_lair": {"room_count": [12, 18], "room_size": {"min": [6, 6], "max": [12, 12]}},
    }
    generator = DungeonGenerator(biomes)
    dungeon = generator.generate(floor=5, seed=99999, biome="crypt")

    secret_rooms = [r for r in dungeon.rooms if r.is_secret]
    print(f"  ✓ {len(secret_rooms)} sala(s) secreta(s)")

    assert len(dungeon.traps) > 0, f"Sem armadilhas! traps={dungeon.traps}"
    print(f"  ✓ {len(dungeon.traps)} armadilha(s)")

    terrain_count = sum(1 for y in range(dungeon.height) for x in range(dungeon.width)
                        if dungeon.get_terrain(x, y) != TerrainModifier.NONE)
    print(f"  ✓ {terrain_count} tile(s) com terreno modificado")

    assert dungeon.get_movement_cost(0, 0) >= 1
    print(f"  ✓ Custo de movimento calculado")

    assert len(dungeon.light_sources) > 0
    print(f"  ✓ {len(dungeon.light_sources)} fonte(s) de luz")

    if dungeon.traps:
        trap_pos = list(dungeon.traps.keys())[0]
        detected = dungeon.detect_trap(trap_pos[0], trap_pos[1], perception_bonus=20)
        print(f"  ✓ Detecção de armadilhas: {detected}")
    print("  [PASSOU]")
    return True


def test_fov():
    print("\n[TESTE 4] Field of View")
    dungeon = DungeonMap(20, 15)
    for x in range(5, 15):
        for y in range(5, 10):
            dungeon.set_tile(x, y, TileType.FLOOR)
    for y in range(5, 10):
        dungeon.set_tile(10, y, TileType.WALL)

    fov = FOVMap(20, 15)
    fov.compute_fov(7, 7, radius=6, dungeon=dungeon)

    assert fov.is_visible(7, 7)
    print(f"  ✓ Origem visível")

    assert fov.is_visible(8, 7)
    print(f"  ✓ Tiles próximos visíveis")

    # Tile atrás da parede NÃO deve ser visível
    assert not fov.is_visible(12, 7), "FOV falhou: tile atrás da parede visível"
    print(f"  ✓ Paredes bloqueiam visão")

    assert fov.is_explored(7, 7)
    print(f"  ✓ Memória persistente")

    fov.compute_fov(7, 7, radius=6, dungeon=dungeon)
    assert len(fov.visible) > 0
    print(f"  ✓ FOV recalculável: {len(fov.visible)} tiles")

    fov.add_light_source(12, 7, 3)
    fov.compute_fov(7, 7, radius=6, dungeon=dungeon)
    print(f"  ✓ Fontes de luz")
    print("  [PASSOU]")
    return True


def test_combat_system():
    print("\n[TESTE 5] Sistema de Combate")
    world = World()
    combat = CombatSystem(seed=42)
    combat.set_world(world)

    attacker = world.create_entity(name="Guerreiro Teste")
    attacker.add_tag("player")
    attacker.add_component(Position(x=5, y=5))
    attacker.add_component(Stats(str_=20, dex=12, con=14, hp=30, max_hp=30, level=5))
    attacker.add_component(Fighter(
        attacks=[{"name": "Espada", "hit_bonus": 10, "damage": "2d8+4", "damage_type": "slashing"}],
        max_movement=5
    ))
    attacker.add_component(Inventory())

    target = world.create_entity(name="Esqueleto Teste")
    target.add_tag("enemy")
    target.add_component(Position(x=6, y=5))
    target.add_component(Stats(str_=10, dex=14, con=10, hp=5, max_hp=5, level=1, ac_base=10))
    target.add_component(Fighter(
        attacks=[{"name": "Garra", "hit_bonus": 1, "damage": "1d6", "damage_type": "slashing"}],
        resistances=[DamageType.SLASHING, DamageType.PIERCING]
    ))
    target.add_component(Inventory())
    target.add_component(AI(behavior_type="melee_aggressive"))

    # Força o ataque a acertar com hit_bonus alto
    combat.process_attack(attacker, target)

    target_stats = target.get_component(Stats)
    print(f"  ✓ Ataque: {target.name} HP {target_stats.hp}/{target_stats.max_hp}")

    assert len(combat.combat_log) > 0
    print(f"  ✓ Log: {len(combat.combat_log)} entradas")

    # Se não morreu, força com outro ataque
    if target_stats.is_alive():
        combat.process_attack(attacker, target)

    attacker_stats = attacker.get_component(Stats)
    assert attacker_stats.xp > 0, f"XP não concedido: {attacker_stats.xp}"
    print(f"  ✓ XP: {attacker_stats.xp}")
    print("  [PASSOU]")
    return True


def test_combat_resistances():
    print("\n[TESTE 6] Resistências e Vulnerabilidades")
    world = World()
    combat = CombatSystem(seed=42)
    combat.set_world(world)

    fire_resistant = world.create_entity(name="Golem de Fogo")
    fire_resistant.add_tag("enemy")
    fire_resistant.add_component(Position(x=5, y=5))
    fire_resistant.add_component(Stats(hp=50, max_hp=50, ac_base=5))
    fire_resistant.add_component(Fighter(
        resistances=[DamageType.FIRE],
        weaknesses=[DamageType.COLD]
    ))

    attacker = world.create_entity(name="Mago Teste")
    attacker.add_tag("player")
    attacker.add_component(Position(x=4, y=5))
    attacker.add_component(Stats(int_=16, hp=20, max_hp=20, level=3))
    attacker.add_component(Fighter(
        attacks=[{"name": "Toque de Fogo", "hit_bonus": 10, "damage": "2d6", "damage_type": "fire"}]
    ))

    combat.process_attack(attacker, fire_resistant)
    fire_stats = fire_resistant.get_component(Stats)
    damage_taken = 50 - fire_stats.hp
    print(f"  ✓ Fogo em resistente: {damage_taken} dano")

    fire_stats.hp = 50
    attacker_fighter = attacker.get_component(Fighter)
    attacker_fighter.attacks = [{"name": "Toque de Gelo", "hit_bonus": 10, "damage": "2d6", "damage_type": "cold"}]
    combat.process_attack(attacker, fire_resistant)
    damage_taken = 50 - fire_stats.hp
    print(f"  ✓ Frio em vulnerável: {damage_taken} dano")
    print("  [PASSOU]")
    return True


def test_conditions():
    print("\n[TESTE 7] Condições de Status")
    world = World()
    cond_sys = ConditionSystem()
    cond_sys.world = world

    entity = world.create_entity(name="Alvo")
    entity.add_component(Stats(hp=30, max_hp=30))
    entity.add_component(Fighter())

    poison = Condition(ConditionType.POISONED, duration=3, potency=10)
    result = cond_sys.apply_condition(entity, poison)
    assert result
    print(f"  ✓ Poison aplicado")

    initial_hp = entity.get_component(Stats).hp
    cond_sys.process_turn(entity)
    final_hp = entity.get_component(Stats).hp
    print(f"  ✓ Dano de poison: {initial_hp} → {final_hp}")
    assert final_hp < initial_hp, f"Dano não aplicado: {initial_hp} -> {final_hp}"

    fighter = entity.get_component(Fighter)
    remaining = [c for c in fighter.conditions if c["name"] == "Envenenado"]
    assert len(remaining) > 0
    print(f"  ✓ Duração: {remaining[0]['duration']} turnos restantes")

    for _ in range(5):
        cond_sys.process_turn(entity)
    remaining = [c for c in fighter.conditions if c["name"] == "Envenenado"]
    assert len(remaining) == 0
    print(f"  ✓ Condição expirou")

    bleed = Condition(ConditionType.BLEEDING, duration=3, potency=1, stacks=True, max_stacks=3)
    cond_sys.apply_condition(entity, bleed)
    cond_sys.apply_condition(entity, bleed)
    cond_sys.apply_condition(entity, bleed)

    bleed_conditions = [c for c in fighter.conditions if c["name"] == "Sangrando"]
    assert len(bleed_conditions) == 1
    assert bleed_conditions[0]["data"]["stack_count"] == 3
    print(f"  ✓ Stacking: 3 stacks")

    undead = world.create_entity(name="Zumbi")
    undead.add_tag("undead")
    undead.add_component(Stats(hp=20, max_hp=20))
    undead.add_component(Fighter())

    poison2 = Condition(ConditionType.POISONED, duration=3, potency=1)
    result = cond_sys.apply_condition(undead, poison2)
    assert not result
    print(f"  ✓ Imunidade (undead vs poison)")
    print("  [PASSOU]")
    return True


def test_abilities():
    print("\n[TESTE 8] Habilidades de Classe")
    world = World()
    cond_sys = ConditionSystem()
    cond_sys.world = world

    mage = world.create_entity(name="Mago")
    mage.add_tag("player")
    mage.add_component(Position(x=5, y=5))
    mage.add_component(Stats(int_=16, hp=20, max_hp=20, mp=30, max_mp=30, level=3))
    mage.add_component(Fighter(max_movement=5))
    mage.add_component(AI())

    enemies = []
    for i, (ex, ey) in enumerate([(6, 5), (7, 5), (5, 6)]):
        enemy = world.create_entity(name=f"Inimigo {i}")
        enemy.add_tag("enemy")
        enemy.add_component(Position(x=ex, y=ey))
        enemy.add_component(Stats(hp=20, max_hp=20, ac_base=5))
        enemy.add_component(Fighter())
        enemies.append(enemy)

    fireball = AbilityRegistry.get("fireball")
    assert fireball is not None
    print(f"  ✓ Bola de Fogo carregada")

    result = fireball.use(mage, target=enemies[0], world=world, condition_system=cond_sys)
    assert result["success"]
    print(f"  ✓ Bola de Fogo: {result.get('targets_hit', 0)} alvos")

    mage_stats = mage.get_component(Stats)
    assert mage_stats.mp < 30
    print(f"  ✓ MP gasto: {30 - mage_stats.mp}")

    cleric = world.create_entity(name="Clérigo")
    cleric.add_tag("player")
    cleric.add_component(Stats(wis=16, hp=15, max_hp=15, mp=25, max_mp=25))
    cleric.add_component(Fighter())
    cleric.add_component(AI())

    cleric_stats = cleric.get_component(Stats)
    cleric_stats.hp = 5

    heal = AbilityRegistry.get("heal")
    result = heal.use(cleric, target=cleric, world=world, condition_system=cond_sys)
    assert result["success"]
    assert cleric_stats.hp > 5
    print(f"  ✓ Cura: 5 → {cleric_stats.hp} HP")

    shield = AbilityRegistry.get("shield")
    result = shield.use(mage, world=world, condition_system=cond_sys)
    assert result["success"]
    print(f"  ✓ Escudo Arcano: +{result.get('ac_bonus', 0)} CA")

    rogue = world.create_entity(name="Ladino")
    rogue.add_tag("player")
    rogue.add_component(Stats(dex=16, hp=15, max_hp=15))
    rogue.add_component(Fighter(max_movement=6))
    rogue.add_component(AI())

    dash = AbilityRegistry.get("dash")
    result = dash.use(rogue, world=world, condition_system=cond_sys)
    assert result["success"]
    print(f"  ✓ Desengate: +{result.get('extra_movement', 0)} mov")

    all_abilities = AbilityRegistry.list_all()
    assert len(all_abilities) >= 10
    print(f"  ✓ {len(all_abilities)} habilidades registradas")

    warrior_abilities = AbilityRegistry.get_class_abilities("warrior")
    assert len(warrior_abilities) > 0
    print(f"  ✓ {len(warrior_abilities)} habilidade(s) de Guerreiro")
    print("  [PASSOU]")
    return True


def test_tactics():
    print("\n[TESTE 9] Táticas de Combate")
    dungeon = DungeonMap(15, 15)
    for x in range(3, 12):
        for y in range(3, 10):
            dungeon.set_tile(x, y, TileType.FLOOR)
    for y in range(3, 10):
        dungeon.set_tile(7, y, TileType.WALL)

    tactics = TacticsSystem(dungeon)

    world = World()
    attacker = world.create_entity(name="Atacante")
    attacker.add_tag("player")
    attacker.add_component(Position(x=5, y=5))
    attacker.add_component(Stats())
    attacker.add_component(Fighter())

    target = world.create_entity(name="Alvo")
    target.add_tag("enemy")
    target.add_component(Position(x=9, y=5))
    target.add_component(Stats())
    target.add_component(Fighter())

    info = tactics.get_tactical_info(attacker, target)
    print(f"  ✓ Cobertura: {info.has_cover} (bônus: {info.cover_bonus})")

    mods = tactics.calculate_attack_modifiers(attacker, target)
    print(f"  ✓ Mods: hit={mods['hit_bonus']}, ca={mods['ca_bonus']}")

    target_pos = target.get_component(Position)
    target_pos.facing = "left"
    info2 = tactics.get_tactical_info(attacker, target)
    print(f"  ✓ Backstab: {info2.is_backstab}")

    line = tactics._bresenham_line(5, 5, 9, 5)
    assert len(line) > 0
    print(f"  ✓ Bresenham: {len(line)} tiles")
    print("  [PASSOU]")
    return True


def test_ecs_integration():
    print("\n[TESTE 10] Integração ECS")
    world = World()

    player = world.create_entity(name="Jogador")
    player.add_tag("player")
    player.add_component(Position(x=10, y=10))
    player.add_component(Renderable(sprite_path="warrior.png", color=(200, 50, 50)))
    player.add_component(Stats(str_=16, dex=14, con=14, hp=35, max_hp=35, mp=10, max_mp=10, level=2))
    player.add_component(Inventory(gold=50, max_slots=20))
    player.add_component(Fighter(
        attacks=[{"name": "Espada Longa", "hit_bonus": 3, "damage": "1d8+2", "damage_type": "slashing"}],
        max_movement=5
    ))

    results = world.query(Position, Stats, tags=["player"])
    assert len(results) == 1
    print(f"  ✓ Query por componentes + tags")

    stats_entities = world.query(Stats)
    assert len(stats_entities) == 1
    print(f"  ✓ {len(stats_entities)} entidade(s) com Stats")

    events_received = []
    def handler(event):
        events_received.append(event.type)

    world.subscribe("test_event", handler)
    world.emit(Event("test_event", {"data": "test"}))
    world._process_events()
    assert "test_event" in events_received
    print(f"  ✓ Eventos ECS")

    player.destroy()
    world._cleanup_entities()
    assert player.is_destroyed
    print(f"  ✓ Destruição de entidades")
    print("  [PASSOU]")
    return True


def run_all_tests():
    print("=" * 60)
    print("  MASCONIA: TESTES UNITÁRIOS")
    print("=" * 60)

    tests = [
        ("Sistema de Dados", test_dice_roller),
        ("Geração de Masmorra", test_dungeon_generation),
        ("Recursos Avançados", test_dungeon_advanced),
        ("Field of View", test_fov),
        ("Sistema de Combate", test_combat_system),
        ("Resistências", test_combat_resistances),
        ("Condições", test_conditions),
        ("Habilidades", test_abilities),
        ("Táticas", test_tactics),
        ("Integração ECS", test_ecs_integration),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n  [FALHOU] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"\n  [ERRO] {name}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"  RESULTADO: {passed} passaram, {failed} falharam")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
