import random 


def random_hex():
    ret = []
    for _ in range(3):
        ret.append('#' + ''.join([random.choice('0123456789abcdef') for _ in range(6)]))
    return ret

def random_task():
    options = [
        'Partnerships',
        'Advertising',
        'Collecting Feedback',
        'Welcoming Members',
        'Creating Events',
        'Engaging with Members'
    ]
    return random.sample(options, 3)

def random_date(month_range=None, day_range=None, year_range=None):
    if month_range is None:
        month_range = (1, 12)
    if year_range is None:
        year_range = (2020, 2023)
    month = random.randint(*month_range)
    if day_range is None:
        if month == 2:
            day_range = (1, 28)
        elif month in (1, 3, 5, 7, 8, 10, 12):
            day_range = (1, 31)
        else:
            day_range = (1, 30)
    day = random.randint(*day_range)
    year = str(random.randint(*year_range))[-2:]
    return f'{month}/{day}/{year}'

def servermade():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2020, 2021))
        if date == '10/16/21' or date in dates:
            continue
        dates.append(date)
    return dates

def anniv():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2021, 2021), month_range=(1, 3))
        if date == '1/30/21' or date in dates:
            continue
        dates.append(date)
    return dates

def hit5k():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2023, 2023), month_range=(8, 9), day_range=(1, 15))
        if date == '9/8/23' or date in dates:
            continue
        dates.append(date)
    return dates

def hit500():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2022, 2022), month_range=(1, 5))
        if date == '2/8/22' or date in dates:
            continue
        dates.append(date)
    return dates

def animal():
    choices = [
        'Dog',
        'Penguin',
        'Shark',
        'Horse',
        'Dolphin',
        'Owl',
        'Gorilla'
    ]
    return random.sample(choices, 3)

def nemibday():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2006, 2006), month_range=(6, 12))
        if date == '8/2/06' or date in dates:
            continue
        dates.append(date)
    return dates

def lunabday():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2007, 2007), month_range=(1, 5))
        if date == '2/23/07' or date in dates:
            continue
        dates.append(date)
    return dates

def musicgenre():
    choices = [
        'Punk Rock',
        'Hip-Hop',
        'Techno',
        'Classical',
        'K-Pop',
        'Fusion Jazz'
    ]
    return random.sample(choices, 3)

def animal2():
    choices = [
        'Fox',
        'Lamb',
        'Goat',
        'Chipmunk',
        'Turtle',
        'Pig',
        'Owl'
    ]
    return random.sample(choices, 3)

def hit690():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2022, 2022), month_range=(4, 4), day_range=(1, 30))
        if date == '4/25/22' or date in dates:
            continue
        dates.append(date)
    return dates

def josh():
    # return three random dates between 2020 and 2022
    dates = []
    while len(dates) < 3:
        date = random_date(year_range=(2021, 2021), month_range=(10, 12))
        if date == '11/14/21' or date in dates:
            continue
        dates.append(date)
    return dates

def songs():
    return [
        "Stressed Out by Twenty One Pilots",
        "Stayin' Alive by Bee Gees",
        "Go by The Black Keys",
    ]

def incidents():
    return [
        "Terrace banned",
        "Fwoggie banning herself",
        "Nemi leaving",
    ]

def notmeg():
    return [
        "Nemi",
        "Vincent",
        "Fwogiie",
    ]

def funpeople():
    return [
        "Sunny, Josh, Fwogiie, Luna, Storch",
        "Luna, Lux, Miku, Molly, Frosting",
        "Nemi, Yura, Levi, Terrace, Tyler",
    ]

def jonas():
    return [
        "Molly came in chat and randomly said Jonas",
        "A Jonas Brothers music vc",
        "Jonas was a word in one of our \"guess the word\" Nitro drops",
    ]

def networks():
    return [
        "Pocky",
        "Haven",
        "Candy Crush",
    ]

def mostpins():
    return [
        'Josh',
        'Fwoggie',
        'Nemi'
    ]

def notyumbum():
    return [
        "Molly",
        "Frosting",
        "Oxytinus",
    ]

def firstthing():
    return [
        'Set the server icon to a cat',
        'Spammed "beeeee" in the general chat',
        'Made a now deleted role called "Luna and Nemi 4 life 😍😍"',
    ]

def longestmod():
    return [
        "Fwogiie",
        "Miku",
        "Sunny",
    ]

def fwoggieadmin():
    return [
        "To code a bot for the server",
"She applied for admin",
"Nemi promoted her on accident",
    ]


def dec2021icon():
    return [
        "Josh",
"Dochi",
"Nemi",
    ]

def paris():
    return [
        "One of Luna's irls",
"One of Nemi's irls",
"The 1st member excluding Luna and Nemi",
    ]


def hit4k():
    return [
        "2/23/23",
"10/19/22",
"9/1/23",
    ]

def motto():
    return [
        "Your go-to sfw aes + art server",
"A place where everyone is included and loved",
".gg/lunaxnemi loves you",
    ]


def headadmins():
    return [
        "Cedar, Levi, Fwogiie",
"Josh, Fwogiie, Miku",
"Tyler, Cedar, Levi",
    ]


def madelunabot():
    return [
        "Fwogiie",
"Luna",
"Nemi",
    ]


def madelumibot():
    return [
        "Stormtorch aka Storch",
"Tyler",
"Molly",
    ]


def fivehundreth():
    return [
        "Molly",
        "Terrace",
        "Josh",
    ]


def madeaibot():
    return [
        "Nemi",
"Levi",
"Frosting",
    ]

questions = [
    ("What is Luna's favorite hex code??", '#cab7ff', random_hex),
    ("What is Nemi's favorite hex code??", "#9900bb", random_hex),
    ("What is Luna's least favorite part of owning a server", "Moderation", random_task),
    ("When was this server made??", "10/16/21", servermade),
    ("When is Nemi and Luna's anniversary??", "1/30/21", anniv),
    ("On what day did we hit 5k members??", "9/8/23", hit5k),
    ("On what day did we hit 500 members??", "2/8/22", hit500),
    ("What is Nemi's favorite animal??", "Cat", animal),
    ("When is Nemi's birthday??", "8/2/06", nemibday),
    ("When is Luna's birthday??", "2/23/07", lunabday),
    ("What is Luna's favorite song??", "Saturday by Twenty One Pilots", songs),
    ("What is Nemi's favorite genre of music??", "Power metal", musicgenre),
    ("What is Luna's favorite animal??", "Bunny", animal2),
    ("Who is Nemi??", "All of the above"),
    ("What happened on 2/22/22??", "The Dochi incident", incidents),
    ("Who made the video \"Luna and Nemi go to Sharkys\"??", "Meg", notmeg),
    ("Who was involved with the magna \"fun\" laude in the gc Lumi Chaos?? **Hint: type Lumi Chaos to see the video**", "Luna, Nemi, Sunny, Molly, Vincent", funpeople),
    ("What is the origin of \"Jonas\"?? **Hint: type \"Jonas\" in chat**", "YAGPDB topic command", jonas),
    ("Who has the most pinned messages in general chat??", "Terrace", mostpins),
    ("What was the first ever server network Lumi Corp joined??", "Meraki", networks),
    ("When did we hit 690 members??", "4/25/22", hit690),
    ("Who made these Luna emotes?? <:LC_Luna_woah_YumBun_NF2U:1118227655116988426> <:LC_Luna_peek_YumBun_NF2U:1118292331192393738> <:LC_Luna_rich_YumBun_NF2U:1118392831317385248>", "YumBun", notyumbum),
    ("What was the first thing Luna did when she created the server??", "Spam ping Nemi with the sticker welcome", firstthing),
    ("When did Josh first join Lumi Corp??", "11/14/21", josh),
    ("Who is the mod who has been with us the longest??", "Soy Sauce", longestmod),
    ("Why did Fwogiie get admin??", "Luna gave her the role so she could try to get the December 2021 server icon to upload", fwoggieadmin),
    ("Who made the server icon for December 2021?? Hint: it's the very first pinned message in chat", "Fwogiie", dec2021icon),
    ("Who was Paris??" ,"An ex mod from 2021", paris),
    ("When did we hit 4k members??", "6/23/23", hit4k),
    ("What is Lumi Corp's motto??", "We <3 you here @ .gg/lunaxnemi", motto),
    ("Who were the 3 head admins before the role got merged with the admin role??", "Fwogiie, Josh, Levi", headadmins),
    ("Who made Lunabot?? **Hint: this bot**", "Stormtorch aka Storch", madelunabot),
    ("Who made Lumi Bot?? **Hint: NOT this bot**", "Fwogiie", madelumibot),
    ("Who is our 500th member??", "Jinny", fivehundreth),
    ("Who helped us get our Luna AI bot??", "Molly", madeaibot)
]
