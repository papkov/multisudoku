import edsudoku


def get_sudoku():
    puzzle = edsudoku.generate(3, 3)
    solved = [[int(puzzle.solution[row, col]) for col in range(puzzle.cols)] for row in range(puzzle.rows)]
    unsolved = [[int(puzzle.problem[row, col]) if puzzle.problem[row, col] != ' ' else 0
                 for col in range(puzzle.cols)] for row in range(puzzle.rows)]
    return {'s': solved, 'u': unsolved}
