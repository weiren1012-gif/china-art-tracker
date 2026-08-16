from .base import BaseScraper
from .christies import ChristiesScraper
from .sothebys import SothebysScraper
from .bonhams import BonhamsScraper
from .dreweatts import DreweattsScraper
from .woolley import WoolleyScraper
from .artcurial import ArtcurialScraper
from .tokyochuo import TokyoChuoScraper
from .seoul import SeoulScraper
from .kauction import KAuctionScraper
from .poly import PolyScraper
from .guardian import GuardianScraper

SCRAPERS = [
    ChristiesScraper(),
    SothebysScraper(),
    BonhamsScraper(),
    DreweattsScraper(),
    WoolleyScraper(),
    ArtcurialScraper(),
    TokyoChuoScraper(),
    SeoulScraper(),
    KAuctionScraper(),
    PolyScraper(),
    GuardianScraper(),
]

BY_NAME = {s.name: s for s in SCRAPERS}


def get_scraper(name):
    return BY_NAME.get(name)
