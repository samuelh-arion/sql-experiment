import json
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import os

# Create charts directory if it doesn't exist
os.makedirs("charts", exist_ok=True)

# Read both results files
with open("results.json", "r") as f:
    data = json.load(f)

with open("results_expanded.json", "r") as f:
    data_expanded = json.load(f)

# Define fixed category orders
QUERY_CATEGORIES = ["department", "leave", "location", "management", "client", "other"]

# Update agent names as requested
AGENT_TYPES = ["Baseline", "Our approach"]  # Changed order to put baseline on the left

# Define Arionkoder color scheme for light theme
COLORS = {
    "background": "#FFFFFF",
    "text": "#000000",
    "primary": "#0000FF",  # Bright blue (0, 0, 255) for "Our approach"
    "secondary": "#8888FF",  # Lighter blue for secondary
    "baseline": "#999999",  # Gray for baseline
    "grid": "#EEEEEE",  # Light gray for grid
}

# Set style for light theme
plt.style.use("seaborn-v0_8-white")
plt.rcParams.update(
    {
        "figure.facecolor": COLORS["background"],
        "axes.facecolor": COLORS["background"],
        "text.color": COLORS["text"],
        "axes.labelcolor": COLORS["text"],
        "xtick.color": COLORS["text"],
        "ytick.color": COLORS["text"],
        "grid.color": COLORS["grid"],
        "figure.titlesize": 14,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
    }
)


def categorize_query(question):
    categories = {
        "department": [
            "department",
            "engineering",
            "sales",
            "hr",
            "design",
            "operations",
        ],
        "leave": ["leave", "vacation", "sick", "birthday", "out of office"],
        "location": ["location", "remote", "london", "new york"],
        "management": ["manager", "report"],
        "client": ["client", "marketing", "apollo"],
    }

    question = question.lower()
    for category, keywords in categories.items():
        if any(keyword in question for keyword in keywords):
            return category
    return "other"


def create_accuracy_chart(data, filename_suffix):
    our_approach_correct = sum(1 for item in data if item["pydantic_agent_correct"])
    baseline_correct = sum(1 for item in data if item["sql_agent_correct"])
    total = len(data)

    plt.figure(figsize=(8, 6))

    # Calculate accuracies - now in order: baseline first, our approach second
    accuracies = [baseline_correct / total * 100, our_approach_correct / total * 100]

    # Set colors for each bar (baseline is gray, our approach is blue)
    bar_colors = [COLORS["baseline"], COLORS["primary"]]

    # Create bars
    bars = plt.bar(AGENT_TYPES, accuracies, color=bar_colors)

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.1f}%",
            ha="center",
            va="bottom",
            color=COLORS["text"],
            fontweight="bold",
        )

    plt.title(f"Query Accuracy ({filename_suffix.capitalize()} Dataset)")
    plt.ylabel("Accuracy (%)")
    plt.ylim(0, 100)  # Ensure y-axis is [0, 100%]
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(
        f"charts/agent_accuracy_{filename_suffix}.png",
        facecolor=COLORS["background"],
        edgecolor="none",
        bbox_inches="tight",
        dpi=300,
    )
    plt.close()


def create_query_distribution(data, filename_suffix):
    query_types = [categorize_query(item["question"]) for item in data]
    type_counts = Counter(query_types)

    # Create ordered counts, filling in zeros for missing categories
    ordered_counts = [type_counts.get(category, 0) for category in QUERY_CATEGORIES]

    plt.figure(figsize=(12, 6))
    bars = plt.bar(QUERY_CATEGORIES, ordered_counts, color=COLORS["primary"])

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height}",
            ha="center",
            va="bottom",
            color=COLORS["text"],
        )

    plt.title(f"Distribution of Query Types ({filename_suffix})")
    plt.ylabel("Number of Queries")
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(
        f"charts/query_distribution_{filename_suffix}.png",
        facecolor=COLORS["background"],
        edgecolor="none",
        bbox_inches="tight",
        dpi=300,
    )
    plt.close()


def create_error_analysis(data, filename_suffix):
    # Count queries with errors
    error_count = sum(1 for item in data if item["error"] is not None)
    no_error_count = sum(1 for item in data if item["error"] is None)

    categories = ["Queries with Errors", "Queries without Errors"]
    counts = [error_count, no_error_count]

    plt.figure(figsize=(8, 6))
    bars = plt.bar(categories, counts, color=[COLORS["secondary"], COLORS["primary"]])

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height}",
            ha="center",
            va="bottom",
            color=COLORS["text"],
        )

    plt.title(f"Query Error Analysis ({filename_suffix})")
    plt.ylabel("Number of Queries")
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(
        f"charts/error_analysis_{filename_suffix}.png",
        facecolor=COLORS["background"],
        edgecolor="none",
        bbox_inches="tight",
        dpi=300,
    )
    plt.close()


def create_comparative_accuracy_chart():
    """
    This function is deprecated as we're now using separate accuracy charts
    for each dataset instead of a side-by-side comparative chart.
    The create_accuracy_chart function now handles this with updated styling.
    """
    # Keep the function body but add a comment that it's deprecated
    # and no longer being called

    # Calculate accuracies for both datasets
    our_approach_orig = sum(1 for item in data if item["pydantic_agent_correct"])
    baseline_orig = sum(1 for item in data if item["sql_agent_correct"])
    total_orig = len(data)

    our_approach_exp = sum(
        1 for item in data_expanded if item["pydantic_agent_correct"]
    )
    baseline_exp = sum(1 for item in data_expanded if item["sql_agent_correct"])
    total_exp = len(data_expanded)

    # Create grouped bar chart - note that the order is now baseline first, our approach second
    orig_accuracy = [
        baseline_orig / total_orig * 100,
        our_approach_orig / total_orig * 100,
    ]
    exp_accuracy = [
        baseline_exp / total_exp * 100,
        our_approach_exp / total_exp * 100,
    ]

    x = range(len(AGENT_TYPES))
    width = 0.35

    plt.figure(figsize=(10, 6))
    bars1 = plt.bar(
        [i - width / 2 for i in x],
        orig_accuracy,
        width,
        label="Original Dataset",
        color=[COLORS["baseline"], COLORS["primary"]],
    )
    bars2 = plt.bar(
        [i + width / 2 for i in x],
        exp_accuracy,
        width,
        label="Expanded Dataset",
        color=[COLORS["baseline"], COLORS["primary"]],
    )

    def autolabel(bars):
        for bar in bars:
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                color=COLORS["text"],
            )

    autolabel(bars1)
    autolabel(bars2)

    plt.ylabel("Accuracy (%)")
    plt.title("Comparative Agent Accuracy Between Datasets")
    plt.xticks(x, AGENT_TYPES)
    plt.legend()
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(
        "charts/comparative_accuracy.png",
        facecolor=COLORS["background"],
        edgecolor="none",
        bbox_inches="tight",
        dpi=300,
    )
    plt.close()


def create_comparative_distribution_chart():
    # Get query distributions for both datasets
    orig_types = Counter([categorize_query(item["question"]) for item in data])
    exp_types = Counter([categorize_query(item["question"]) for item in data_expanded])

    # Convert to percentages
    orig_total = len(data)
    exp_total = len(data_expanded)

    orig_percentages = [
        orig_types.get(cat, 0) / orig_total * 100 for cat in QUERY_CATEGORIES
    ]
    exp_percentages = [
        exp_types.get(cat, 0) / exp_total * 100 for cat in QUERY_CATEGORIES
    ]

    x = range(len(QUERY_CATEGORIES))
    width = 0.35

    plt.figure(figsize=(12, 6))
    bars1 = plt.bar(
        [i - width / 2 for i in x],
        orig_percentages,
        width,
        label="Original Dataset",
        color=COLORS["primary"],
    )
    bars2 = plt.bar(
        [i + width / 2 for i in x],
        exp_percentages,
        width,
        label="Expanded Dataset",
        color=COLORS["secondary"],
    )

    def autolabel(bars):
        for bar in bars:
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                color=COLORS["text"],
            )

    autolabel(bars1)
    autolabel(bars2)

    plt.ylabel("Percentage of Queries")
    plt.title("Comparative Query Type Distribution")
    plt.xticks(x, QUERY_CATEGORIES, rotation=45)
    plt.legend()
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(
        "charts/comparative_distribution.png",
        facecolor=COLORS["background"],
        edgecolor="none",
        bbox_inches="tight",
        dpi=300,
    )
    plt.close()


def create_combined_accuracy_chart():
    """
    Creates a single chart with both original and expanded dataset accuracy
    charts side by side for easy comparison.
    """
    # Calculate accuracies for original dataset
    our_approach_orig = sum(1 for item in data if item["pydantic_agent_correct"])
    baseline_orig = sum(1 for item in data if item["sql_agent_correct"])
    total_orig = len(data)

    orig_accuracies = [
        baseline_orig / total_orig * 100,
        our_approach_orig / total_orig * 100,
    ]

    # Calculate accuracies for expanded dataset
    our_approach_exp = sum(
        1 for item in data_expanded if item["pydantic_agent_correct"]
    )
    baseline_exp = sum(1 for item in data_expanded if item["sql_agent_correct"])
    total_exp = len(data_expanded)

    exp_accuracies = [
        baseline_exp / total_exp * 100,
        our_approach_exp / total_exp * 100,
    ]

    # Create a figure with two subplots side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))

    # Set colors for each bar (baseline is gray, our approach is blue)
    bar_colors = [COLORS["baseline"], COLORS["primary"]]

    # Plot original dataset in the left subplot
    bars1 = ax1.bar(AGENT_TYPES, orig_accuracies, color=bar_colors, width=0.5)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("Accuracy (%)", fontsize=12)
    ax1.set_title("Original Dataset", fontsize=14, pad=10)
    ax1.grid(True, alpha=0.2, axis="y")

    # Plot expanded dataset in the right subplot
    bars2 = ax2.bar(AGENT_TYPES, exp_accuracies, color=bar_colors, width=0.5)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Accuracy (%)", fontsize=12)
    ax2.set_title("Expanded Dataset", fontsize=14, pad=10)
    ax2.grid(True, alpha=0.2, axis="y")

    # Add value labels on top of bars
    def autolabel(ax, bars):
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 1,  # Add a small offset for better spacing
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                color=COLORS["text"],
                fontweight="bold",
                fontsize=12,
            )

    autolabel(ax1, bars1)
    autolabel(ax2, bars2)

    # Remove top and right spines for cleaner look
    for ax in [ax1, ax2]:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="both", which="major", labelsize=11)

    plt.tight_layout()
    plt.subplots_adjust(wspace=0.25)  # Add space between subplots

    # Save the figure
    plt.savefig(
        "charts/combined_accuracy.png",
        facecolor=COLORS["background"],
        edgecolor="none",
        bbox_inches="tight",
        dpi=300,
    )
    plt.close()


def print_dataset_stats(data, dataset_name):
    print(f"\nSummary Statistics for {dataset_name}:")
    total = len(data)
    our_approach_correct = sum(1 for item in data if item["pydantic_agent_correct"])
    baseline_correct = sum(1 for item in data if item["sql_agent_correct"])

    print(f"Total number of queries: {total}")
    print(f"Our approach accuracy: {our_approach_correct/total*100:.1f}%")
    print(f"Baseline accuracy: {baseline_correct/total*100:.1f}%")

    # Query type distribution
    query_types = [categorize_query(item["question"]) for item in data]
    type_counts = Counter(query_types)
    print("\nQuery type distribution:")
    # Use fixed order for printing
    for category in QUERY_CATEGORIES:
        count = type_counts.get(category, 0)
        percentage = (count / total) * 100
        print(f"{category}: {count} queries ({percentage:.1f}%)")


# Generate charts for original dataset
create_accuracy_chart(data, "original")
create_query_distribution(data, "original")
create_error_analysis(data, "original")

# Generate charts for expanded dataset
create_accuracy_chart(data_expanded, "expanded")
create_query_distribution(data_expanded, "expanded")
create_error_analysis(data_expanded, "expanded")

# Generate comparative distribution chart (not accuracy chart)
# create_comparative_accuracy_chart()  # Deprecated in favor of separate charts
create_comparative_distribution_chart()

# Generate combined accuracy chart
create_combined_accuracy_chart()

# Print summary statistics for both datasets
print_dataset_stats(data, "Original Dataset")
print_dataset_stats(data_expanded, "Expanded Dataset")
