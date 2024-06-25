import math


class Fps:
    def __init__(self, frametimes: list[float]) -> None:
        self.sorted_frametimes = sorted(frametimes, reverse=True)

        # cache values
        self.total = sum(frametimes)
        self.length = len(frametimes)
        self.mean = 1000 / (self.total / self.length)

    def lows(self, value: float) -> float:
        current_total = 0.0

        for frametime in self.sorted_frametimes:
            current_total += frametime
            if current_total >= value / 100 * self.total:
                return 1000 / frametime
        return 0.0

    def percentile(self, value: float) -> float:
        return 1000 / self.sorted_frametimes[math.ceil(value / 100 * self.length) - 1]

    def stdev(self) -> float:
        squared_deviations = sum((1000 / framerate - self.mean) ** 2 for framerate in self.sorted_frametimes)
        return math.sqrt(squared_deviations / (self.length - 1))  # bessel's correction

    def maximum(self) -> float:
        return 1000 / self.sorted_frametimes[-1]

    def minimum(self) -> float:
        return 1000 / self.sorted_frametimes[0]

    def average(self) -> float:
        return self.mean
