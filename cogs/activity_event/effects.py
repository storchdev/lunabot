
class Powerup:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.n = None 
        self.name = None 
        self.log_name = None


class Multiplier(Powerup):
    def __init__(self, n, start, end):
        super().__init__(start, end)
        self.n = n 
        self.name = 'Multiplier'
        self.log_name = 'multi_powerup'
    

class CooldownReducer(Powerup):
    def __init__(self, cd, start, end):
        super().__init__(start, end)
        self.n = cd 
        self.name = 'Cooldown Reducer'
        self.log_name = 'cd_powerup'
