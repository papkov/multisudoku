# multisudoku
Multiplayer concurrent sudoku

University of Tartu. Distributed systems course. Fall 2017

* Mikhail Papkov

* Elizaveta Korotkova

* Vladislav Fedyukov

* Alina Vorontseva

## Setup user manual
To use the application successfully, run the following commands:

`sudo apt-get install python-tk`

`pip install -r requirements`

To start the application, run the file `main.py`.

## Interface user manual

To open a new game window, run `main.py`.

![A newly created game window](https://raw.githubusercontent.com/papkov/multisudoku/master/pics/new_window.png)

To act as a server, select a username and click 'Host'.
(The username has to be a valid one: not longer than 8 alphanumeric characters, no spaces.)
To connect to an existing session,
write in the host's address and your username, and click 'Join';
a list of available sessions will appear on the left-hand side of the window,
click on one of the items to join a game.
It is possible to act as a host and join one's own session at the same time.
It also possible to host own session and join someone else's simultaneously.

![After a server was created](https://raw.githubusercontent.com/papkov/multisudoku/master/pics/host_session.png)

To create a new puzzle to solve, click 'New game'. After that (or after joining an existing
session) a sudoku board will be generated for you (or fetched from someone else's session),
and you can start playing.

![A gameboard](https://raw.githubusercontent.com/papkov/multisudoku/master/pics/game.png)

Every right answer will give the player 1 point, and the right number will be saved in the puzzle.
Every wrong answer will take out 1 point, and the answer will not be saved.
The points are displayed in 'Leaderboard' on the left-hand side.
