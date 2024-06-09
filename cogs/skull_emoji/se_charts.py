from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO

from datetime import datetime
from pytz import timezone
from discord import File


params = {
    "ytick.color" : "w",
    "xtick.color" : "w",
    "axes.labelcolor" : "w",
    "axes.edgecolor" : "w",
    "figure.dpi": 300,
}
plt.rcParams.update(params)


async def plot_data(bot, data):
    buf = await bot.loop.run_in_executor(None, plot_data_sync, data)
    return File(fp=buf, filename='plot.png')    

def plot_data_sync(data):
    """
    Plot data synchronously.
    :param data: A list of tuples of the form (datetime, value).
    :return: A BytesIO object containing the plot.
    """
    # Convert the data to a list of datetime objects and a list of values.

    # Create the plot.
    fig = plt.figure(figsize=(8, 5))
    # set background colo
    fig.set_facecolor('#36393f')

    ax = fig.add_subplot(1, 1, 1)
    ax.set_facecolor('#36393f')

    # add legends

    # ax.plot([datetime.fromtimestamp(t[0]) for t in data[0][1]], [t[1] for t in data[0][1]], color='#cab7ff')
    # if len(data) > 1:
    #     ax.plot([datetime.fromtimestamp(t[0]) for t in data[1][1]], [t[1] for t in data[1][1]], color='#9900bb')

    # Format the x axis.
    legends = []
    i = 0
    colors = {
        'bunny': '#cab7ff',
        'kitty': '#9900bb'
    }
    for t in data:
        legends.append(t[0].name)
        color = colors[t[0].name]
        ax.plot([datetime.fromtimestamp(t[0]) for t in data[i][1]], [t[1] for t in data[i][1]], color=color)
        i += 1

    ax.legend(legends)

    # ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d\n%H:%M', tz=timezone('US/Central')))

    # Rotate the x axis labels.
    fig.autofmt_xdate()

    # Save the plot to a BytesIO object.
    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)

    return buf


if __name__ == '__main__':
    test_data = [
        ('bunny', 
        [(1619097600, 0),
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
        (1619125600, 200),]
         ) 
    ]
    buf = plot_data_sync(test_data)
    from PIL import Image 
    img = Image.open(buf)
    img.show()
