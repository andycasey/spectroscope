#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

""" sick, the spectroscopic inference crank. """

__author__ = "Andy Casey <arc@ast.cam.ac.uk>"

import argparse
import cPickle as pickle
import logging
import os

import numpy as np
import yaml
import json

import sick

logger = logging.getLogger("sick")

def parser(input_args=None):
    """
    Command line parser for *sick*.
    """

    parser = argparse.ArgumentParser(
        description="sick, the spectroscopic inference crank", epilog="Use "
            "'sick-model COMMAND -h' for information on a specific command."
            " Documentation and examples available at "
            "https://github.com/andycasey/sick")

    # Create a parent subparser.
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "-v", "--verbose", dest="verbose", action="store_true", default=False,
        help="Vebose logging mode.")
    parent_parser.add_argument(
        "--clobber", dest="clobber", action="store_true", default=False, 
        help="Overwrite existing files if they already exist.")
    parent_parser.add_argument(
        "--debug", dest="debug", action="store_true", default=False,
        help="Enable debug mode. Any suppressed exception will be re-raised.")
    parent_parser.add_argument(
        "-o", "--output_dir", dest="output_dir", nargs="?", type=str,
        help="Directory for the files that will be created. If not given, this"
        " defaults to the current working directory.", default=os.getcwd())

    # Create subparsers.
    subparsers = parser.add_subparsers(title="command", dest="command",
        description="Specify the action to perform.")

    # Create parser for the aggregate command
    aggregate_parser = subparsers.add_parser(
        "aggregate", parents=[parent_parser],
        help="Aggregate many result files into a single tabular FITS file.")
    aggregate_parser.add_argument("output_filename", type=str,
        help="Output filename to aggregate results into.")
    aggregate_parser.add_argument("result_filenames", nargs="+",
        help="The YAML result filenames to combine.")
    aggregate_parser.set_defaults(func=aggregate)

    # Create parser for the estimate command
    estimate_parser = subparsers.add_parser(
        "estimate", parents=[parent_parser],
        help="Compute a point estimate of the model parameters given the data.")
    estimate_parser.add_argument(
        "model", type=str,
        help="The model filename in YAML-style formatting.")
    estimate_parser.add_argument(
        "spectrum_filenames", nargs="+",
        help="Filenames of (observed) spectroscopic data.")
    estimate_parser.add_argument(
        "--filename-prefix", "-p", dest="filename_prefix",
        type=str, help="The filename prefix to use for the output files.")
    estimate_parser.add_argument(
        "--no-plots", dest="plotting", action="store_false", default=True,
        help="Disable plotting.")
    estimate_parser.add_argument(
        "--plot-format", "-pf", dest="plot_format", action="store", type=str, 
        default="png", help="Format for output plots (default: %(default)s)")
    estimate_parser.set_defaults(func=estimate)

    # Create parser for the optimise command
    optimise_parser = subparsers.add_parser(
        "optimise", parents=[parent_parser],
        help="Optimise the model parameters, given the data.")
    optimise_parser.add_argument(
        "model", type=str,
        help="The model filename in YAML-style formatting.")
    optimise_parser.add_argument(
        "spectrum_filenames", nargs="+",
        help="Filenames of (observed) spectroscopic data.")
    optimise_parser.add_argument(
        "--filename-prefix", "-p", dest="filename_prefix", type=str,
        help="The filename prefix to use for the output files.")
    optimise_parser.add_argument(
        "--no-plots", dest="plotting", action="store_false", default=True,
        help="Disable plotting.")
    optimise_parser.add_argument(
        "--plot-format", "-pf", dest="plot_format", action="store", type=str,
        default="png", help="Format for output plots (default: %(default)s)")
    optimise_parser.set_defaults(func=optimise)

    # Create parser for the infer command
    infer_parser = subparsers.add_parser(
        "infer", parents=[parent_parser],
        help="Infer the model parameters, given the data.")
    infer_parser.add_argument(
        "model", type=str,
        help="The model filename in YAML-style formatting.")
    infer_parser.add_argument(
        "spectrum_filenames", nargs="+",
        help="Filenames of (observed) spectroscopic data.")
    infer_parser.add_argument(
        "--filename-prefix", "-p", dest="filename_prefix", type=str,
        help="The filename prefix to use for the output files.")
    infer_parser.add_argument(
        "--no-chains", dest="save_chain_files", action="store_false",
        default=True, help="Do not save the chains to disk.", )
    infer_parser.add_argument(
        "--no-plots", dest="plotting", action="store_false", default=True,
        help="Disable plotting.")
    infer_parser.add_argument(
        "--plot-format", "-pf", dest="plot_format", action="store", type=str,
        default="png", help="Format for output plots (default: %(default)s)")
    infer_parser.set_defaults(func=infer)

    args = parser.parse_args(input_args)
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # Create a default filename prefix based on the input filename arguments
    if args.command.lower() in ("estimate", "optimise", "infer") \
    and args.filename_prefix is None:
        args.filename_prefix = _default_output_prefix(args.spectrum_filenames)

        handler = logging.FileHandler("{}.log".format(
            os.path.join(args.output_dir, args.filename_prefix)))
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
        # Check plot formats.
        if args.plotting:
            import matplotlib.pyplot as plt
            fig = plt.figure()
            available = fig.canvas.get_supported_filetypes().keys()
            plt.close(fig)

            if args.plot_format.lower() not in available:
                raise ValueError("plotting format {0} is unavailable: Options "\
                    "are: {1}".format(
                        args.plot_format.lower(), ", ".join(available)))
    return args


def _prefix(args, f):
    return os.path.join(args.output_dir, "-".join([args.filename_prefix, f]))


def _ok_to_clobber(args, filenames):

    if args.clobber:
        return True

    paths = [_prefix(args, _) for _ in filenames]
    exists = map(os.path.exists, paths)
    if any(exists):
        raise IOError("expected output filename(s) already exist and we have "
            "been told not to clobber them: {}".format(", ".join(
                [path for path, e in zip(paths, exists) if e])))
    return True


def _default_output_prefix(filenames):
    """
    Return a default filename prefix for output files based on the input files.

    :param filenames:
        The input filename(s):

    :type filenames:
        str or list of str

    :returns:
        The extensionless common prefix of the input filenames:

    :rtype:
        str
    """

    if isinstance(filenames, (str, )):
        filenames = [filenames]
    common_prefix, ext = os.path.splitext(os.path.commonprefix(
        map(os.path.basename, filenames)))
    common_prefix = common_prefix.rstrip("_-")
    return common_prefix if len(common_prefix) > 0 else "sick"


def _pre_solving(args, expected_output_files):

    # Check that it will be OK to clobber existing files.
    _ok_to_clobber(args, expected_output_files)

    # Load the model and data.
    data = map(sick.specutils.Spectrum1D.load, args.spectrum_filenames)
    model = sick.models.Model(args.model)

    logger.info("Model configuration:")
    map(logger.info, yaml.safe_dump(model._configuration, stream=None,
        allow_unicode=True, default_flow_style=False).split("\n"))

    # Define headers that we want in the results filename 
    metadata = {
        "model": model.hash, 
        "input_filenames": ", ".join(args.spectrum_filenames),
        "sick_version": sick.__version__,
        "headers": {}
    }

    # Get some headers from the first spectrum.
    for header in ("RA", "DEC", "COMMENT", "ELAPSED", "FIBRE_NUM", "LAT_OBS",
        "LONG_OBS", "MAGNITUDE","NAME", "OBJECT", "UTEND", "UTDATE", "UTSTART"):
        metadata["headers"][header] = data[0].headers.get(header, None)

    return (model, data, metadata)


def _write_output(filename, output):
    #with open(filename, "w+") as fp:
    #    yaml.safe_dump(metadata, stream=fp, allow_unicode=True,
    #        default_flow_style=False)

    with open(filename, "w+") as fp:
        fp.write(json.dumps(output, indent=2))
    logger.info("Results written to {}".format(filename))
    return True


def estimate(args, **kwargs):
    """
    Return a point estimate of the model parameters theta given the data.
    """

    expected_output_files = kwargs.pop("expected_output_files", None)
    if not expected_output_files:
        expected_output_files = ["estimate.yaml"]
        if args.plotting:
            expected_output_files.extend(
                ["projection-estimate.{}".format(args.plot_format)])
        
    model, data, metadata = _pre_solving(args, expected_output_files)

    try:
        theta, chisq, dof, model_fluxes = model.estimate(data, full_output=True,
            debug=args.debug)

    except:
        logger.exception("Failed to estimate model parameters")
        raise

    logger.info("Estimated model parameters are:")
    map(logger.info, ["\t{0}: {1:.3f}".format(p, v) for p, v in theta.items()])
    logger.info("With a chi-sq value of {0:.1f} (reduced {1:.1f}; DOF {2:.1f})"\
        .format(chisq, chisq/dof, dof))

    metadata["estimated"] = {
        "theta": theta,
        "chi_sq": chisq,
        "dof": dof,
        "r_chi_sq": chisq/dof
    }

    if args.plotting:
        fig = sick.plot.spectrum(data, model_flux=model_fluxes)
        filename = _prefix(args, "projection-estimate.{}".format(
            args.plot_format))
        fig.savefig(filename)
        logger.info("Created figure {}".format(filename))

    if kwargs.pop("__return_result", False):
        return (model, data, metadata, theta)

    # Write the result to file.
    _write_output(_prefix(args, "estimate.yaml"), metadata)
    return None


def optimise(args, **kwargs):
    """
    Optimise the model parameters.
    """

    expected_output_files = kwargs.pop("expected_output_files", None)
    if not expected_output_files:
        expected_output_files = ["optimised.yaml"]
        if args.plotting:
            expected_output_files.extend([
                "projection-estimate.{}".format(args.plot_format),
                "projection-optimised.{}".format(args.plot_format)
            ])
        
    # Estimate the model parameters, unless they are already specified.
    model = sick.models.Model(args.model)
    initial_theta = model._configuration.get("initial_theta", {})
    if len(set(model.parameters).difference(initial_theta)) == 0:
        model, data, metadata = _pre_solving(args, expected_output_files)

    else:
        model, data, metadata, initial_theta = estimate(args, 
            expected_output_files=expected_output_files, __return_result=True)

    try:
        theta, chisq, dof, model_fluxes = model.optimise(data, 
            initial_theta=initial_theta, full_output=True, debug=args.debug)

    except:
        logger.exception("Failed to optimise model parameters")
        raise

    metadata["optimised"] = {
        "theta": theta,
        "chi_sq": chisq,
        "dof": dof,
        "r_chi_sq": chisq/dof
    }

    logger.info("Optimised model parameters are:")
    map(logger.info, ["\t{0}: {1:.3f}".format(p, v) for p, v in theta.items()])
    logger.info("With a chi-sq value of {0:.1f} (reduced {1:.1f}; DOF {2:.1f})"\
        .format(chisq, chisq/dof, dof))

    if args.plotting:
        fig = sick.plot.spectrum(data, model_flux=model_fluxes)
        filename = _prefix(args, "projection-optimised.{}".format(
            args.plot_format))
        fig.savefig(filename)
        logger.info("Created figure {}".format(filename))

    if kwargs.pop("__return_result", False):
        return (model, data, metadata, theta)

    # Write the results to file.
    _write_output(_prefix(args, "optimised.yaml"), metadata)
    return None



def infer(args):
    """
    Infer the model parameters.
    """

    expected_output_files = ["inferred.yaml"]
    if args.plotting:
        expected_output_files.extend([each.format(args.plot_format) \
            for each in "chain.{}", "corner.{}", "acceptance-fractions.{}",
            "autocorrelation.{}"])

    # Optimise them first.
    model, data, metadata, optimised_theta = optimise(args,
        expected_output_files=expected_output_files, __return_result=True)

    # Get the inference parameters from the model configuration.
    kwargs = model._configuration.get("infer", {})
    [kwargs.pop(k, None) \
        for k in ("debug", "full_output", "initial_proposal", "data")]

    try:
        theta, chains, lnprobability, acceptance_fractions, sampler, info_dict \
            = model.infer(data, initial_proposal=optimised_theta, 
                full_output=True, debug=args.debug, **kwargs)

    except:
        logger.exception("Failed to infer model parameters")
        raise

    metadata["inferred"] = {
        "theta": theta,
        "chi_sq": info_dict["chi_sq"],
        "dof": info_dict["dof"],
        "r_chi_sq": info_dict["chi_sq"]/info_dict["dof"]
    }

    logger.info("Inferred parameters are:")
    map(logger.info, ["\t{0}: {1:.3f} ({2:+.3f}, {3:+.3f})".format(
        p, v[0], v[1], v[2]) for p, v in theta.items()])

    # Write the results to file.
    _write_output(_prefix(args, "inferred.yaml"), metadata)

    # Write the chains, etc to disk.
    if args.save_chain_files:
        filename = _prefix(args, "chains.pkl")
        with open(filename, "wb") as f:
            pickle.dump(
                (chains, lnprobability, acceptance_fractions, info_dict), f, -1)
        logger.info("Saved chains to {}".format(filename))

    # Make plots.
    if args.plotting:
        burn = info_dict["burn"]

        # Any truth values to plot?
        truths = model._configuration.get("truths", None)
        if truths:
            truths = [truths.get(p, np.nan) for p in model.parameters]

        # Labels?
        labels = model._configuration.get("labels", {})
        labels = [labels.get(p, p) for p in info_dict["parameters"]]
        
        # Acceptance fractions.
        fig = sick.plot.acceptance_fractions(acceptance_fractions,
            burn_in=burn)
        _ = _prefix(args, "acceptance-fractions.{}".format(args.plot_format))
        fig.savefig(_)
        logger.info("Saved acceptance fractions figure to {}".format(_))

        # Autocorrelation.
        fig = sick.plot.autocorrelation(chains, burn_in=burn)
        _ = _prefix(args, "auto-correlation.{}".format(args.plot_format))
        fig.savefig(_)
        logger.info("Saved auto-correlation figure to {}".format(_))

        # Chains.
        fig = sick.plot.chains(chains, labels=labels, burn_in=burn,
            truths=truths)
        _ = _prefix(args, "chains.{}".format(args.plot_format))
        fig.savefig(_)
        logger.info("Saved chains figure to {}".format(_))

        # Corner plots (astrophysical + all).
        N = len(model.grid_points.dtype.names)
        fig = sick.plot.corner(chains[:, burn:, :N].reshape(-1, N),
            labels=labels, truths=truths[:N] if truths else None)
        _ = _prefix(args, "corner.{}".format(args.plot_format))
        fig.savefig(_)
        logger.info("Saved corner plot (astrophysical parameters) to {}"\
            .format(_))

        if len(model.parameters) > N:
            fig = sick.plot.corner(chains[:, burn:, :].reshape(
                -1, len(model.parameters)), labels=labels,
                truths=truths)
            _ = _prefix(args, "corner-all.{}".format(args.plot_format))
            fig.savefig(_)
            logger.info("Saved corner plot (all parameters) to {}".format(_))

        # Projections.
        # Note here we need to scale the chains back to redshift so the data
        # are generated properly.
        fig = sick.plot.projection(
            data, model, chains=chains[:, burn:, :]/info_dict["scales"])
        _ = _prefix(args, "projection.{}".format(args.plot_format))
        fig.savefig(_)
        logger.info("Saved projection plot to {}".format(_))

    return None


def aggregate(args):


    raise NotImplementedError

    
def main():
    """ Parse arguments and execute the correct sub-parser. """

    args = parser()
    return args.func(args)


if __name__ == "__main__":
    main()
