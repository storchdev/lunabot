from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
from discord import File
from discord.ext.commands import Context
from matplotlib import pyplot as plt

from .constants import *

if TYPE_CHECKING:
    from bot import LunaBot


__all__ = ("DataPoint", "TeamSeries", "PlotData", "plot_data")

type DataPoint = tuple[datetime, int]
type TeamSeries = tuple[str, list[DataPoint]]
type PlotData = list[TeamSeries]


params = {
    "ytick.color": "w",
    "xtick.color": "w",
    "axes.labelcolor": "w",
    "axes.edgecolor": "w",
    "figure.dpi": 300,
}
plt.rcParams.update(params)


async def plot_data(ctx: Context, tz: str, data: PlotData) -> File:
    bot: "LunaBot" = ctx.bot

    buf = await bot.loop.run_in_executor(None, _plot_data_sync, data, tz)
    return File(fp=buf, filename="plot.png")


def _plot_data_sync(data: PlotData, tz: str):
    """
    Plot data synchronously.
    :param data: A list of tuples of the form (datetime, value).
    :return: A BytesIO object containing the plot.
    """
    # Convert the data to a list of datetime objects and a list of values.

    # Create the plot.
    fig = plt.figure(figsize=(8, 5))

    # set background color
    fig.set_facecolor("none")
    ax = fig.add_subplot(1, 1, 1)
    ax.set_facecolor("none")

    # handle default tz
    # if tz is None:
    #     tz = "America/Chicago"
    #     fig.text(
    #         0.05,
    #         0.05,
    #         "You have not set a timezone with !settz. Defaulting to CST.",
    #         fontsize=10,
    #         color="w",
    #     )

    # plot data
    legends = []
    colors = {"mistletoe": "#599a60", "poinsettia": "#eb5454"}
    for i, t in enumerate(data):
        # t[0]: team name
        # t[1]: [(datetime, int)]

        legends.append(t[0])
        color = colors[t[0]]
        ax.plot(
            [t_[0] for t_ in data[i][1]],
            [t_[1] for t_ in data[i][1]],
            color=color,
        )

    ax.legend(legends)

    # format x-axis
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%a %-m/%-d\n%-I:%M %p", tz=ZoneInfo(tz))
    )

    # Rotate the x axis labels.
    fig.autofmt_xdate()

    # Save the plot to a BytesIO object.
    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)

    return buf


if __name__ == "__main__":
    test_data = [
        (
            "bunny",
            [
                (datetime.fromtimestamp(t[0]), t[1])
                for t in [
                    (1619097600, 0),
                    (1619097900, 1),
                    (1619098200, 2),
                    (1619098500, 3),
                    (1619098800, 4),
                    (1619099100, 5),
                    (1619099400, 6),
                    (1619099700, 7),
                    (1619100000, 8),
                    (1619100300, 9),
                    (1619100600, 10),
                    (1619100900, 11),
                    (1619101200, 12),
                    (1619101500, 13),
                    (1619101800, 14),
                    (1619102100, 15),
                    (1619102400, 16),
                    (1619102700, 17),
                    (1619103000, 18),
                    (1619103300, 19),
                    (1619103600, 20),
                    (1619103900, 21),
                    (1619104200, 22),
                    (1619104500, 23),
                    (1619104800, 24),
                    (1619105100, 25),
                    (1619105400, 26),
                    (1619105700, 27),
                    (1619106000, 28),
                    (1619106300, 29),
                    (1619106600, 30),
                    (1619106900, 31),
                    (1619107200, 32),
                    (1619107500, 33),
                    (1619107800, 34),
                    (1619108100, 35),
                    (1619108400, 36),
                    (1619108700, 37),
                    (1619109000, 38),
                    (1619109300, 39),
                    (1619109600, 40),
                    (1619109900, 41),
                    (1619110200, 42),
                    (1619110500, 43),
                    (1619110800, 44),
                    (1619111100, 45),
                    (1619111400, 46),
                    (1619111700, 47),
                    (1619112000, 48),
                    (1619112300, 49),
                    (1619125600, 200),
                ]
            ],
        )
    ]
    buf = plot_data_sync(test_data)
    from PIL import Image

    img = Image.open(buf)
    img.show()
