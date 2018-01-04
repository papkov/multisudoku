# multisudoku
Multiplayer concurrent sudoku v0.0.2

University of Tartu. Distributed systems course. Fall 2017

* Mikhail Papkov [@papkov](https://github.com/papkov)

* Elizaveta Korotkova [@lisskor](https://github.com/lisskor)

* Vladislav Fedyukov [@cherrybonch](https://github.com/cherrybonch)

* Alina Vorontseva [@AlinaVorontseva](https://github.com/AlinaVorontseva)

# Contents

1. [Setup](#setup)

2. [Architecture](#arch)

3. [How to play?](#howto)

  1. [Host the server](#host)
  
  2. [Join the server](#join)
  
  3. [Guess the number](#guess)

## Setup user manual <a name="setup"/>

System requirements: Python 2.7, Linux (Windows can be OK; broadcast outside the local machine does not work properly from Windows to Linux)

To use the application successfully, run the following commands:

`sudo apt-get install python-tk`

`pip install -r requirements`

To start the application, run the file `main.py`.

## Architecture <a name="arch"/>

App uses **remote procedure calls (RPC)** and **broadcast** as main communication protocols

One app can be used as server and player simultaneously in parallel threads. In order to play player should connect to one of existing servers or create their own. Available servers in the network broadcasting their addresses. Once a server is created it will immediately be discovered by all players online.

On server side, there is a proxy server that answers on clients' RPC requests to set a name, set new game, get current state and guess number. There can be several servers in one network, they should act through different ports. RPC works as follows. Client gives parameters into corresponding function (if they are needed), and server does the job and replies if operation was successful. 

Implementing functions im RPC paradigm helped us to get rid of communication protocols, now all communication between client and server is done by RPC calls or broadcasts.

## How to play? <a name="howto"/>

To open a new game window, run `python main.py`. You will see the board:

![A newly created game window](https://raw.githubusercontent.com/papkov/multisudoku/master/pics/new_window_2.png)

### Host the server <a name="host"/>
To act as a server, select a username and click \[Host\]. After that you should see a dialog and select the local network to act in (usually there are several network interfaces: near each of it is written IP address in related local network)

![Hosting dialog](https://raw.githubusercontent.com/papkov/multisudoku/master/pics/select_network.png)


### Join the server <a name="join"/>
To connect to an existing session (or one that was just created), write in your username, and click \[Join\]; a list of available servers will appear in dialog box, click on one of the items to join a game. 
It is possible to act as a host and join one's own session at the same time. It also possible to host own session and join someone else's simultaneously.

![After a server was created](https://raw.githubusercontent.com/papkov/multisudoku/master/pics/select_server.png)

If the game was already started you will see updated board with the numbers. Otherwise you should click \[New game\]
After that (or after joining an existing session) a sudoku board will be generated for you (or fetched from someone else's session),
and you can start playing.

### Guess the number <a name="guess"/>
![A gameboard](https://raw.githubusercontent.com/papkov/multisudoku/master/pics/game_2.png)

Every right answer will give the player 1 point, and the right number will be saved in the puzzle.
Every wrong answer will take out 1 point, and the answer will not be saved.
The points are displayed in 'Leaderboard' on the left-hand side.

The game will end when the board will be full.
