"""
GameState: máquina de estados que gerencia todas as telas do jogo.

Estados:
  • MAIN_MENU: tela inicial com opções
  • CLASS_SELECT: escolha de classe
  • DUNGEON_GENERATION: geração da masmorra (com loading)
  • PLAYER_TURN: turno do jogador (movimento + ação)
  • ENEMY_TURN: turno dos inimigos (IA executa)
  • COMBAT_ANIMATION: animações de ataque/dano
  • INVENTORY: gerenciamento de itens
  • SHOP: loja do comerciante
  • REST_SITE: sala de descanso
  • LEVEL_UP: escolha de melhorias
  • GAME_OVER: tela de morte
  • VICTORY: tela de vitória
  • DAILY_CHALLENGE: daily challenge com seed fixa

Por que máquina de estados?
  → Cada estado tem lógica, input e renderização próprias.
  → Transições são explícitas e controladas.
  → Facilita pausar/salvar o estado atual.
  → Permite adicionar novos estados (cutscenes, diálogos) facilmente.
"""
import json
import os
from typing import Optional, Dict, Any, Callable
from datetime import datetime

import pygame

from ecs.world import World
from utils.constants import GameState as State
from config.settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, FPS,
    MAX_FLOOR, DRAGON_SOUL_PER_FLOOR, DRAGON_SOUL_PER_BOSS, DRAGON_SOUL_PER_MINIBOSS
)
from dungeon.generator import DungeonGenerator, DungeonMap
from combat.system import CombatSystem
from systems.render_system import RenderSystem
from systems.movement_system import MovementSystem
from systems.ai_system import AISystem
from entities.player import PlayerFactory
from entities.enemy import EnemyFactory
from components.position import Position
from components.stats import Stats
from components.inventory import Inventory
from components.fighter import Fighter


class GameStateManager:
    """
    Gerenciador de estados do jogo.

    Attributes:
        screen: Surface principal do Pygame.
        clock: Clock para controle de FPS.
        font: Fonte padrão.
        current_state: Estado atual.
        world: World ECS.
        dungeon: DungeonMap atual.
        player: Entidade do jogador.
        combat_system: CombatSystem.
        render_system: RenderSystem.
        movement_system: MovementSystem.
        ai_system: AISystem.
        dungeon_generator: DungeonGenerator.
        player_factory: PlayerFactory.
        enemy_factory: EnemyFactory.
        floor: Andar atual.
        seed: Seed da run atual.
        meta_progression: Dados persistentes (Alma do Dragão, desbloqueios).
    """

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.title_font = pygame.font.Font(None, 48)

        self.current_state = State.MAIN_MENU
        self.previous_state = None

        # ECS
        self.world = World()
        self.dungeon: Optional[DungeonMap] = None
        self.player: Optional[Any] = None

        # Systems
        self.combat_system = CombatSystem()
        self.render_system = RenderSystem(screen, self.font)
        self.movement_system = MovementSystem()
        self.ai_system = AISystem(self.movement_system)

        # Registra systems no world
        self.world.register_system(self.render_system)
        self.world.register_system(self.movement_system)
        self.world.register_system(self.ai_system)
        # CombatSystem não precisa ser registrado como system (é chamado explicitamente)

        # Factories
        self.dungeon_generator = self._create_dungeon_generator()
        self.player_factory = PlayerFactory()
        self.enemy_factory = EnemyFactory()

        # Progressão
        self.floor = 1
        self.seed = 0
        self.meta_progression = self._load_meta_progression()

        # UI state
        self.selected_class = None
        self.hovered_tile = None
        self.selected_tile = None
        self.movement_range = []
        self.attack_range = []
        self.turn_ended = False
        self.animating = False

        # Event subscriptions
        self._setup_event_handlers()

    def _create_dungeon_generator(self) -> DungeonGenerator:
        """Cria o gerador de masmorra com dados de biomas."""
        path = os.path.join(os.path.dirname(__file__), "..", "data", "biomes.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                biomes = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            biomes = {}
        return DungeonGenerator(biomes)

    def _load_meta_progression(self) -> Dict:
        """Carrega progressão persistente do jogador."""
        save_path = os.path.join(os.path.dirname(__file__), "..", "save", "progress.json")
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "dragon_souls": 0,
                "unlocked_classes": ["warrior", "rogue", "mage", "cleric"],
                "unlocked_relics": ["broken_dice"],
                "best_run_floor": 0,
                "total_runs": 0,
                "total_kills": 0,
            }

    def _save_meta_progression(self):
        """Salva progressão persistente."""
        save_dir = os.path.join(os.path.dirname(__file__), "..", "save")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "progress.json")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.meta_progression, f, indent=2)

    def _setup_event_handlers(self):
        """Registra handlers de eventos do ECS."""
        self.world.subscribe("entity_died", self._on_entity_died)
        self.world.subscribe("xp_gained", self._on_xp_gained)
        self.world.subscribe("boss_phase_changed", self._on_boss_phase)

    def _on_entity_died(self, event):
        """Handler quando uma entidade morre."""
        victim = event.data.get("victim")
        if victim and victim.has_tag("boss"):
            # Boss derrotado → ganha Alma do Dragão
            souls = DRAGON_SOUL_PER_BOSS
            self._award_dragon_souls(souls)
        elif victim and victim.has_tag("enemy"):
            self.meta_progression["total_kills"] = self.meta_progression.get("total_kills", 0) + 1

    def _on_xp_gained(self, event):
        """Handler de XP ganho."""
        if event.data.get("leveled_up"):
            self.transition_to(State.LEVEL_UP)

    def _on_boss_phase(self, event):
        """Handler de mudança de fase de boss."""
        # TODO: efeitos visuais e sonoros de mudança de fase
        pass

    def _award_dragon_souls(self, amount: int):
        """Concede Alma do Dragão ao jogador."""
        self.meta_progression["dragon_souls"] = self.meta_progression.get("dragon_souls", 0) + amount
        if self.player:
            inv = self.player.get_component(Inventory)
            if inv:
                inv.add_dragon_souls(amount)

    # ── Transições de Estado ───────────────────────────────────

    def transition_to(self, new_state: State):
        """Transiciona para um novo estado."""
        self.previous_state = self.current_state
        self.current_state = new_state

        # Inicialização de estado
        if new_state == State.DUNGEON_GENERATION:
            self._generate_dungeon()
        elif new_state == State.PLAYER_TURN:
            self._start_player_turn()
        elif new_state == State.ENEMY_TURN:
            self._start_enemy_turn()
        elif new_state == State.GAME_OVER:
            self._handle_game_over()
        elif new_state == State.VICTORY:
            self._handle_victory()

    def _generate_dungeon(self):
        """Gera a masmorra para o andar atual."""
        # Determina bioma baseado no andar
        if self.floor <= 5:
            biome = "crypt"
        elif self.floor <= 10:
            biome = "crystal_caverns"
        else:
            biome = "dragon_lair"

        # Seed: seed base + floor (para runs reproduzíveis)
        floor_seed = self.seed + self.floor * 1000

        self.dungeon = self.dungeon_generator.generate(
            floor=self.floor,
            seed=floor_seed,
            biome=biome
        )

        # Injeta mapa no MovementSystem
        self.movement_system.set_dungeon_map(self.dungeon)

        # Spawna inimigos nas salas
        self._spawn_enemies()

        # Posiciona jogador na sala de spawn
        if self.dungeon.rooms:
            spawn_room = self.dungeon.rooms[0]
            spawn_pos = self.dungeon.find_empty_tile(spawn_room)
            if spawn_pos and self.player:
                pos = self.player.get_component(Position)
                pos.x, pos.y = spawn_pos

        # Atualiza câmera
        if self.player:
            self.render_system.set_camera_target(self.player.get_component(Position))

        # Transiciona para turno do jogador
        self.transition_to(State.PLAYER_TURN)

    def _spawn_enemies(self):
        """Spawna inimigos nas salas da masmorra."""
        for room in self.dungeon.rooms:
            if room.room_type.value == 1:  # SPAWN
                continue

            biome = self.dungeon.biome

            for enemy_data in room.enemies:
                x, y = enemy_data["x"], enemy_data["y"]

                if room.room_type.value == 5:  # BOSS
                    enemy = self.enemy_factory.create_enemy(
                        self.world, "", biome, x, y, is_boss=True
                    )
                elif room.room_type.value == 4:  # ELITE
                    enemy = self.enemy_factory.create_random_enemy(
                        self.world, biome, x, y, difficulty="elite"
                    )
                else:
                    enemy = self.enemy_factory.create_random_enemy(
                        self.world, biome, x, y, difficulty="normal"
                    )

    def _start_player_turn(self):
        """Inicia o turno do jogador."""
        if not self.player:
            return

        fighter = self.player.get_component(Fighter)
        if fighter:
            fighter.reset_turn()

        # Calcula range de movimento
        self.movement_range = self.movement_system.get_movement_range(
            self.player, fighter.max_movement if fighter else 5
        )
        self.attack_range = self.movement_system.get_attack_range(
            self.player, attack_range=1
        )
        self.turn_ended = False

    def _start_enemy_turn(self):
        """Inicia o turno dos inimigos."""
        # O AISystem.process_enemy_turn() é chamado no update()
        pass

    def _handle_game_over(self):
        """Processa morte do jogador."""
        self.meta_progression["total_runs"] = self.meta_progression.get("total_runs", 0) + 1

        # Concede Alma do Dragão parcial pelo progresso
        souls = self.floor * DRAGON_SOUL_PER_FLOOR
        self._award_dragon_souls(souls)

        self._save_meta_progression()

    def _handle_victory(self):
        """Processa vitória (derrotou o Wyrm)."""
        self.meta_progression["total_runs"] = self.meta_progression.get("total_runs", 0) + 1

        # Bônus de vitória
        souls = 500 + self.floor * DRAGON_SOUL_PER_FLOOR
        self._award_dragon_souls(souls)

        # Atualiza recorde
        if self.floor > self.meta_progression.get("best_run_floor", 0):
            self.meta_progression["best_run_floor"] = self.floor

        self._save_meta_progression()

    # ── Loop Principal ───────────────────────────────────────────

    def handle_input(self, event: pygame.event.Event):
        """Processa input do jogador baseado no estado atual."""
        if self.current_state == State.MAIN_MENU:
            self._handle_menu_input(event)
        elif self.current_state == State.CLASS_SELECT:
            self._handle_class_select_input(event)
        elif self.current_state == State.PLAYER_TURN:
            self._handle_player_turn_input(event)
        elif self.current_state == State.INVENTORY:
            self._handle_inventory_input(event)
        elif self.current_state == State.GAME_OVER:
            self._handle_game_over_input(event)

    def _handle_menu_input(self, event: pygame.event.Event):
        """Input do menu principal."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                self.transition_to(State.CLASS_SELECT)
            elif event.key == pygame.K_2:
                # Daily challenge
                today_seed = int(datetime.now().strftime("%Y%m%d"))
                self.seed = today_seed
                self.transition_to(State.CLASS_SELECT)
            elif event.key == pygame.K_3:
                # Sair
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _handle_class_select_input(self, event: pygame.event.Event):
        """Input da tela de seleção de classe."""
        if event.type == pygame.KEYDOWN:
            classes = ["warrior", "rogue", "mage", "cleric"]
            for i, cls in enumerate(classes):
                if event.key == getattr(pygame, f"K_{i+1}"):
                    if cls in self.meta_progression.get("unlocked_classes", []):
                        self.selected_class = cls
                        self._start_new_run()
                        return
            if event.key == pygame.K_ESCAPE:
                self.transition_to(State.MAIN_MENU)

    def _start_new_run(self):
        """Inicia uma nova run."""
        # Limpa o mundo
        self.world.clear()
        self.floor = 1

        if self.seed == 0:
            import random
            self.seed = random.randint(0, 999999)

        self.combat_system.set_seed(self.seed)

        # Cria jogador
        self.player = self.player_factory.create_player(
            self.world, self.selected_class, x=0, y=0
        )

        # Gera masmorra
        self.transition_to(State.DUNGEON_GENERATION)

    def _handle_player_turn_input(self, event: pygame.event.Event):
        """Input durante o turno do jogador."""
        if not self.player:
            return

        pos = self.player.get_component(Position)
        fighter = self.player.get_component(Fighter)

        if event.type == pygame.KEYDOWN:
            # Movimento
            dx, dy = 0, 0
            if event.key == pygame.K_UP or event.key == pygame.K_w:
                dy = -1
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                dy = 1
            elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                dx = -1
            elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                dx = 1

            if dx != 0 or dy != 0:
                # Verifica se há inimigo no tile alvo
                target_x = pos.x + dx
                target_y = pos.y + dy

                # Busca inimigo no tile
                enemy = None
                for entity in self.world.query(Position, tags=["enemy"]):
                    epos = entity.get_component(Position)
                    if epos.x == target_x and epos.y == target_y:
                        enemy = entity
                        break

                if enemy:
                    # Ataca
                    self.combat_system.process_attack(self.player, enemy)
                else:
                    # Move
                    self.movement_system.move_entity(self.player, dx, dy)
                    self.render_system.set_camera_target(pos)

                # Atualiza ranges
                self.movement_range = self.movement_system.get_movement_range(
                    self.player, fighter.max_movement if fighter else 5
                )
                self.attack_range = self.movement_system.get_attack_range(self.player)

            # Inventário
            elif event.key == pygame.K_i:
                self.transition_to(State.INVENTORY)

            # Esperar (pular turno)
            elif event.key == pygame.K_SPACE:
                self._end_player_turn()

            # Debug
            elif event.key == pygame.K_F1:
                self.render_system.show_debug = not self.render_system.show_debug

        elif event.type == pygame.MOUSEMOTION:
            # Hover sobre tiles
            mx, my = event.pos
            # Converte pixel → tile
            cam_x, cam_y = self.render_system.camera_offset
            tile_x = (mx + cam_x) // TILE_SIZE
            tile_y = (my + cam_y) // TILE_SIZE
            self.hovered_tile = (tile_x, tile_y)

    def _end_player_turn(self):
        """Finaliza o turno do jogador e passa para os inimigos."""
        self.turn_ended = True
        self.transition_to(State.ENEMY_TURN)

    def _handle_inventory_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.transition_to(State.PLAYER_TURN)

    def _handle_game_over_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.transition_to(State.MAIN_MENU)

    def update(self):
        """Atualiza a lógica do estado atual."""
        dt = self.clock.tick(FPS) / 1000.0

        if self.current_state == State.ENEMY_TURN:
            self.ai_system.update(dt)
            # Após IA executar, volta para o jogador
            if not self.animating:
                self.transition_to(State.PLAYER_TURN)

        elif self.current_state == State.COMBAT_ANIMATION:
            # Processa animações pendentes
            if self.combat_system.animation_queue:
                # TODO: executar animações
                self.combat_system.animation_queue.clear()
            else:
                self.transition_to(self.previous_state or State.PLAYER_TURN)

        # Atualiza systems ECS
        self.world.update(dt)

        # Verifica morte do jogador
        if self.player:
            stats = self.player.get_component(Stats)
            if stats and not stats.is_alive():
                self.transition_to(State.GAME_OVER)

    def render(self):
        """Renderiza o estado atual."""
        if self.current_state in (State.PLAYER_TURN, State.ENEMY_TURN):
            self._render_dungeon()
        elif self.current_state == State.MAIN_MENU:
            self._render_main_menu()
        elif self.current_state == State.CLASS_SELECT:
            self._render_class_select()
        elif self.current_state == State.INVENTORY:
            self._render_inventory()
        elif self.current_state == State.GAME_OVER:
            self._render_game_over()
        elif self.current_state == State.VICTORY:
            self._render_victory()
        elif self.current_state == State.DUNGEON_GENERATION:
            self._render_loading()
        elif self.current_state == State.LEVEL_UP:
            self._render_level_up()

        pygame.display.flip()

    def _render_dungeon(self):
        """Renderiza a masmorra em jogo."""
        self.render_system.render(self.screen)

        # Destaca range de movimento
        if self.current_state == State.PLAYER_TURN and self.movement_range:
            from config.settings import COLOR_MOVE_RANGE
            self.render_system.highlight_tiles(self.screen, self.movement_range, COLOR_MOVE_RANGE)

        # Destaca range de ataque
        if self.current_state == State.PLAYER_TURN and self.attack_range:
            from config.settings import COLOR_ATTACK_RANGE
            self.render_system.highlight_tiles(self.screen, self.attack_range, COLOR_ATTACK_RANGE)

        # UI de turno
        turn_text = "SEU TURNO" if self.current_state == State.PLAYER_TURN else "TURNO DOS INIMIGOS"
        color = (100, 255, 100) if self.current_state == State.PLAYER_TURN else (255, 100, 100)
        text = self.font.render(turn_text, True, color)
        self.screen.blit(text, (SCREEN_WIDTH - 200, 10))

        # Log de combate
        log = self.combat_system.get_combat_log(5)
        for i, line in enumerate(reversed(log)):
            log_text = self.small_font.render(line, True, (180, 180, 180))
            self.screen.blit(log_text, (10, 10 + i * 14))

    def _render_main_menu(self):
        """Renderiza o menu principal."""
        self.screen.fill((15, 15, 25))

        # Título
        title = self.title_font.render("WYRMFALL", True, (200, 50, 50))
        subtitle = self.font.render("Chronicles of the Broken Dice", True, (180, 160, 100))

        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 150))
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 200))

        self.screen.blit(title, title_rect)
        self.screen.blit(subtitle, subtitle_rect)

        # Opções
        options = [
            "[1] Nova Run",
            "[2] Daily Challenge",
            "[3] Sair",
        ]

        for i, opt in enumerate(options):
            text = self.font.render(opt, True, (220, 220, 220))
            rect = text.get_rect(center=(SCREEN_WIDTH // 2, 300 + i * 40))
            self.screen.blit(text, rect)

        # Stats
        souls = self.meta_progression.get("dragon_souls", 0)
        runs = self.meta_progression.get("total_runs", 0)
        stats_text = self.small_font.render(
            f"Almas: {souls} | Runs: {runs} | Recorde: Andar {self.meta_progression.get('best_run_floor', 0)}",
            True, (140, 140, 140)
        )
        self.screen.blit(stats_text, (10, SCREEN_HEIGHT - 30))

    def _render_class_select(self):
        """Renderiza a tela de seleção de classe."""
        self.screen.fill((15, 15, 25))

        title = self.title_font.render("Escolha sua Classe", True, (220, 220, 220))
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 80))
        self.screen.blit(title, title_rect)

        classes = [
            ("warrior", "Guerreiro", "Mestre das armas. Alto HP, armadura pesada."),
            ("rogue", "Ladino", "Especialista em furtividade. Críticos frequentes."),
            ("mage", "Mago", "Manipulador arcano. Dano mágico de área."),
            ("cleric", "Clérigo", "Servo divino. Cura aliados, repele mortos-vivos."),
        ]

        for i, (cls_id, name, desc) in enumerate(classes):
            y = 180 + i * 100

            # Caixa de seleção
            box_color = (60, 60, 80) if cls_id in self.meta_progression.get("unlocked_classes", []) else (40, 40, 40)
            pygame.draw.rect(self.screen, box_color, (100, y, SCREEN_WIDTH - 200, 80))
            pygame.draw.rect(self.screen, (100, 100, 120), (100, y, SCREEN_WIDTH - 200, 80), 2)

            # Nome e descrição
            name_text = self.font.render(f"[{i+1}] {name}", True, (220, 220, 220))
            desc_text = self.small_font.render(desc, True, (180, 180, 180))

            self.screen.blit(name_text, (120, y + 15))
            self.screen.blit(desc_text, (120, y + 45))

        # Instruções
        instr = self.small_font.render("ESC para voltar", True, (140, 140, 140))
        self.screen.blit(instr, (10, SCREEN_HEIGHT - 30))

    def _render_inventory(self):
        """Renderiza o inventário."""
        self.screen.fill((20, 20, 30))

        title = self.font.render("INVENTÁRIO", True, (220, 220, 220))
        self.screen.blit(title, (20, 20))

        if self.player:
            inv = self.player.get_component(Inventory)
            if inv:
                # Equipados
                eq_text = self.font.render("Equipado:", True, (180, 180, 180))
                self.screen.blit(eq_text, (20, 60))

                y = 85
                for slot, item in inv.equipped.items():
                    slot_name = str(slot).split(".")[-1]
                    text = self.small_font.render(f"  {slot_name}: {item.get('name', '?')}", True, (200, 200, 200))
                    self.screen.blit(text, (20, y))
                    y += 20

                # Mochila
                bag_text = self.font.render(f"Mochila ({len(inv.items)}/{inv.max_slots}):", True, (180, 180, 180))
                self.screen.blit(bag_text, (20, y + 20))

                y += 45
                for item in inv.items:
                    text = self.small_font.render(f"  • {item.get('name', '?')}", True, (200, 200, 200))
                    self.screen.blit(text, (20, y))
                    y += 18

                # Moedas
                gold_text = self.font.render(f"Ouro: {inv.gold} | Almas: {inv.dragon_souls}", True, (255, 215, 0))
                self.screen.blit(gold_text, (20, SCREEN_HEIGHT - 50))

        esc = self.small_font.render("ESC para fechar", True, (140, 140, 140))
        self.screen.blit(esc, (10, SCREEN_HEIGHT - 25))

    def _render_game_over(self):
        """Renderiza tela de Game Over."""
        self.screen.fill((20, 10, 10))

        title = self.title_font.render("GAME OVER", True, (200, 50, 50))
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 200))
        self.screen.blit(title, title_rect)

        floor_text = self.font.render(f"Você chegou ao Andar {self.floor}", True, (220, 220, 220))
        floor_rect = floor_text.get_rect(center=(SCREEN_WIDTH // 2, 280))
        self.screen.blit(floor_text, floor_rect)

        souls = self.meta_progression.get("dragon_souls", 0)
        souls_text = self.font.render(f"Almas do Dragão: {souls}", True, (255, 215, 0))
        souls_rect = souls_text.get_rect(center=(SCREEN_WIDTH // 2, 320))
        self.screen.blit(souls_text, souls_rect)

        cont = self.font.render("Pressione ESPAÇO para continuar", True, (180, 180, 180))
        cont_rect = cont.get_rect(center=(SCREEN_WIDTH // 2, 400))
        self.screen.blit(cont, cont_rect)

    def _render_victory(self):
        """Renderiza tela de vitória."""
        self.screen.fill((10, 20, 10))

        title = self.title_font.render("VITÓRIA!", True, (50, 200, 50))
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 200))
        self.screen.blit(title, title_rect)

        sub = self.font.render("O Wyrm foi derrotado!", True, (220, 220, 220))
        sub_rect = sub.get_rect(center=(SCREEN_WIDTH // 2, 280))
        self.screen.blit(sub, sub_rect)

        souls = self.meta_progression.get("dragon_souls", 0)
        souls_text = self.font.render(f"Almas do Dragão: {souls}", True, (255, 215, 0))
        souls_rect = souls_text.get_rect(center=(SCREEN_WIDTH // 2, 320))
        self.screen.blit(souls_text, souls_rect)

        cont = self.font.render("Pressione ESPAÇO para continuar", True, (180, 180, 180))
        cont_rect = cont.get_rect(center=(SCREEN_WIDTH // 2, 400))
        self.screen.blit(cont, cont_rect)

    def _render_loading(self):
        """Renderiza tela de carregamento."""
        self.screen.fill((15, 15, 25))

        text = self.title_font.render("Gerando Masmorra...", True, (200, 200, 200))
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(text, rect)

        # Barra de progresso animada
        progress = (pygame.time.get_ticks() % 1000) / 1000.0
        bar_width = 400
        bar_height = 20
        bar_x = (SCREEN_WIDTH - bar_width) // 2
        bar_y = SCREEN_HEIGHT // 2 + 50

        pygame.draw.rect(self.screen, (40, 40, 60), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(self.screen, (100, 150, 200), (bar_x, bar_y, int(bar_width * progress), bar_height))

    def _render_level_up(self):
        """Renderiza tela de level up."""
        self.screen.fill((15, 15, 30))

        title = self.title_font.render("LEVEL UP!", True, (200, 200, 50))
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)

        if self.player:
            stats = self.player.get_component(Stats)
            if stats:
                level_text = self.font.render(f"Nível {stats.level} alcançado!", True, (220, 220, 220))
                level_rect = level_text.get_rect(center=(SCREEN_WIDTH // 2, 220))
                self.screen.blit(level_text, level_rect)

                hp_text = self.font.render(f"HP: {stats.max_hp} (+{stats.max_hp - stats.hp} curado)", True, (100, 200, 100))
                hp_rect = hp_text.get_rect(center=(SCREEN_WIDTH // 2, 260))
                self.screen.blit(hp_text, hp_rect)

        cont = self.font.render("Pressione ESPAÇO para continuar", True, (180, 180, 180))
        cont_rect = cont.get_rect(center=(SCREEN_WIDTH // 2, 350))
        self.screen.blit(cont, cont_rect)

    def __repr__(self):
        return f"GameStateManager(state={self.current_state.name}, floor={self.floor})"
