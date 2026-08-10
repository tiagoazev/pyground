Feature: The game window boots and renders
  As a player
  I want the game to open and draw the board on screen
  So that I can actually play it instead of seeing a crash

  Background:
    Given a headless pygame display

  Scenario: The UI initialises without crashing
    Then the screen and the score font should be ready

  Scenario: A frame renders the snake on the LCD board
    Given a rendered frame of a fresh game
    Then the snake head cell should be drawn in the LCD foreground color
    And an empty cell should be drawn in the LCD background color

  Scenario: The game over overlay renders without crashing
    Given a rendered frame of a game that is over
    Then the frame should have been drawn
