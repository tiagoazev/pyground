Feature: Nokia-style Snake game mechanics
  As a player
  I want the snake to behave like the classic Nokia 3310 Snake
  So that the game feels authentic

  Background:
    Given a new snake game with width 20 and height 15

  Scenario: The snake moves forward each step
    When the snake moves 1 step
    Then the snake head should be at position 11,7

  Scenario: The snake grows when it eats food
    Given food is placed directly in front of the snake
    When the snake moves 1 step
    Then the snake length should be 4
    And the score should be 1

  Scenario: The snake does not grow when it does not eat food
    When the snake moves 1 step
    Then the snake length should be 3
    And the score should be 0

  Scenario: The snake dies when it hits the left wall
    Given the snake is heading left right next to the left wall
    When the snake moves 1 step
    Then the game should be over

  Scenario: The snake dies when it hits the top wall
    Given the snake is heading up right next to the top wall
    When the snake moves 1 step
    Then the game should be over

  Scenario: The snake dies when it collides with its own body
    Given the snake is set up to collide with itself
    When the snake moves 1 step
    Then the game should be over

  Scenario: The snake cannot reverse directly into itself
    When the snake attempts to reverse direction
    Then the snake direction should still be RIGHT

  Scenario: Food never spawns on top of the snake
    Then the food position should not overlap the snake body

  Scenario: The game can be reset after game over
    Given the snake is set up to collide with itself
    And the snake moves 1 step
    When the game is reset
    Then the game should not be over
    And the score should be 0
