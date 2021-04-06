import logging
import os
import typing
from time import sleep

from source import utilities

log: typing.Union[logging.Logger, None] = None


def sanityChecks() -> bool:
    try:
        if not os.path.exists("data"):
            os.makedirs("data")
    except Exception as e:
        print(e)
        return False
    return True


def main():
    from source import bot

    log.info("Ready, calling bot.py")
    bot.run()


if __name__ == "__main__":
    logo = r"""
__________        .__              .___.__        
\______   \_____  |  | _____     __| _/|__| ____  
 |     ___/\__  \ |  | \__  \   / __ | |  |/    \ 
 |    |     / __ \|  |__/ __ \_/ /_/ | |  |   |  \
 |____|    (____  /____(____  /\____ | |__|___|  /
                \/          \/      \/         \/ """

    logo = logo.replace("r", "\033[0m")
    logo = logo.replace("c", "\033[96m")
    print(logo)
    sleep(1)
    sanityChecks()
    log = utilities.getLog("Main")
    log.info("Logging system started")
    main()
