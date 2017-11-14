import sudoku_maker as sm
import random


def get_sudoku(complexity=5):
    solved = sm.make(9)
    unsolved = []
    for row in solved:
        # Remove random numbers (with repetitions) from each row
        remove = [random.randint(0, len(row)-1) for i in range(complexity)]
        urow = [n if i not in remove else 0 for i, n in enumerate(row)]
        unsolved.append(urow)

    return {"s": solved, "u": unsolved}

