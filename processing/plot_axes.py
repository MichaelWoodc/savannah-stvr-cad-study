"""Discrete guest/room/count axes; approved capacity uses even-numbered ticks."""
import math
from matplotlib.ticker import MaxNLocator, MultipleLocator, StrMethodFormatter

def discrete_axis(ax,label='',approved=False):
    text=label.lower()
    even=approved or (('approved' in text or 'licensed guest capacity' in text) and 'minus' not in text and 'difference' not in text)
    if even:
        lo,hi=ax.get_xlim()
        step=2*max(1,math.ceil((hi-lo)/22))
        ax.xaxis.set_major_locator(MultipleLocator(step))
    else:
        ax.xaxis.set_major_locator(MaxNLocator(nbins=12,integer=True))
    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:.0f}'))
