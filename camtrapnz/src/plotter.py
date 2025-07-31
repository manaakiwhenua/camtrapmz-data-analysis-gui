import matplotlib.pyplot as plt
import pandas as pd

def plot_trap_rates(df, filename, dpi=300, figsize=(10, 6), show=False):
    """
    Plots and optionally saves a camera trap rate bar chart per species.
    
    Parameters:
    - df (DataFrame): trap rates with columns ["Species", "Rate_per100CamDays", "MinusBar", "PlusBar"]
    - filename (str): path to save the plot image
    - dpi (int): resolution of the saved image
    - figsize (tuple): size of the plot in inches
    - show (bool): if True, displays the plot; otherwise, just saves
    """

    plt.figure(figsize=figsize)
    plt.bar(df["Species"], df["Rate_per100CamDays"],
            yerr=[df["MinusBar"], df["PlusBar"]],
            capsize=5, color="skyblue", edgecolor="black")

    plt.ylabel("Trap Rate per 100 Camera Days")
    plt.xlabel("Species")
    plt.title("Camera Trap Rate per Species")
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(filename, dpi=dpi, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()
