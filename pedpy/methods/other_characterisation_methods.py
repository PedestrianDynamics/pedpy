"""Module containing functions to compute pair distribution function."""

import warnings
from typing import Tuple

import numpy as np
import numpy.typing as npt
import pandas
from scipy.spatial.distance import cdist

from pedpy.column_identifier import FRAME_COL, ID_COL, X_COL, Y_COL
from pedpy.data.trajectory_data import TrajectoryData


def compute_pair_distibution_function(
    *,
    traj_data: TrajectoryData,
    radius_bin_size: float,
    randomisation_stacking: int = 1,
) -> Tuple[npt.NDArray[np.float16], npt.NDArray[np.float16]]:
    """
    Computes the pair distribution function g(r) for a given set of trajectory data.

    This function calculates the spatial distribution of positions :math:`g(r)`
    For a variable :math:`r`, the pdf is given by the probability that two pedestrians are separated
    by :math:`r` normalized by the probability :math:`PNI(r)` that two non-interacting pedestrians
    are separated by :math:`r`, specifically

    .. math::
        g(r) = P(r)/PNI(r),

    Args:
    - traj_data: TrajectoryData, an object containing the trajectories.
    - radius_bin_size: float, the size of the bins for the radial distribution function in the same units as the positions.
    - randomisation_stacking: int, Number of time the dataset will be stacked before being randomly shuffled to exact distances of non-interacting pedestrians. Larger stacking number will lead to closer approximation of true pairwise distribution of non-interacting pedestrians but with also increase computation cost.


    Returns:
    - Tuple[np.ndarray, np.ndarray]: A tuple of two numpy arrays. The first array contains the bin edges (excluding the first bin edge),
      and the second array contains the values of the pair distribution function :math:`g(r)` for each bin.
    """
    df = traj_data.data

    # Create Dataframe with all pairwise distances
    dist_pd_array = calculate_data_frame_pair_dist(df)

    # Concatenate the working dataframe df  to match the number of randomization cycles
    concatenated_random_df = pandas.concat(
        [df] * randomisation_stacking, ignore_index=True
    )
    # Scramble time-information to mitigate finite-size effects and calculate pairwise distances of scrambled dataset
    concatenated_random_df.frame = concatenated_random_df.frame.sample(
        frac=1
    ).reset_index(drop=True)
    dist_pd_ni_array = calculate_data_frame_pair_dist(concatenated_random_df)

    ## Create the bin for data
    radius_bins = np.arange(0, dist_pd_array.max(), radius_bin_size)

    # Calculate pair distibution: g(r)
    ## Actual distribution
    pd_bins = pandas.cut(dist_pd_array, radius_bins)
    pd_bins_normalised = (pd_bins.value_counts().sort_index().to_numpy()) / len(
        dist_pd_array
    )  # Normalising by the number of pairwise distances in the dataframe
    ## Scrambled distribution
    pd_ni_bins = pandas.cut(dist_pd_ni_array, radius_bins)
    pd_ni_bins_normalised = (
        pd_ni_bins.value_counts().sort_index().to_numpy()
    ) / len(
        dist_pd_ni_array
    )  # Normalising by the number of pairwise distances in the dataframe

    # Suppress warnings
    warnings.filterwarnings("ignore")

    try:
        with np.errstate(divide="raise"):
            pair_distribution = pd_bins_normalised / pd_ni_bins_normalised
        warnings.filterwarnings("default")  # reset wrnings values

    except FloatingPointError:
        warnings.filterwarnings("default")  # reset wrnings values
        pair_distribution = pd_bins_normalised / pd_ni_bins_normalised
        warning_message = "Random probability distribution contains null values, try using larger dx or more randomization cycles."
        warnings.warn(warning_message)

    return radius_bins[1:], pair_distribution


def calculate_data_frame_pair_dist(
    df: pandas.DataFrame,
) -> npt.NDArray[np.float16]:
    distances_list = []

    for _, frame_df in df.groupby(FRAME_COL):
        unique_ids = frame_df[ID_COL].unique()
        N_ids = len(unique_ids)
        if N_ids > 1:
            x_values = frame_df[X_COL].values
            y_values = frame_df[Y_COL].values
            coordinates = np.stack((x_values, y_values), axis=-1)
            # Calculate pairwise distances for the current frame using cdist
            frame_distances = cdist(
                coordinates, coordinates, metric="euclidean"
            )

            # Extract the upper triangle without the diagonal
            distances_upper_triangle = frame_distances[
                np.triu_indices_from(frame_distances, k=1)
            ]

            distances_list.extend(distances_upper_triangle)

    return np.array(distances_list)