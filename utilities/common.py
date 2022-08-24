import hist
import pathlib
import argparse
import logging

wremnants_dir = f"{pathlib.Path(__file__).parent}/../wremnants"
data_dir = f"{wremnants_dir}/data/"

wprocs = ["WplusmunuPostVFP", "WminusmunuPostVFP", "WminustaunuPostVFP", "WplustaunuPostVFP"]
zprocs = ["ZmumuPostVFP", "ZtautauPostVFP"]
vprocs = wprocs+zprocs

# standard regular axes
axis_eta = hist.axis.Regular(48, -2.4, 2.4, name = "eta")
axis_pt = hist.axis.Regular(29, 26., 55., name = "pt")
#ptV_binning = [0, 2, 3, 4, 4.75, 5.5, 6.5, 8, 9, 10, 12, 14, 16, 18, 20, 23, 27, 32, 40, 55, 100]
ptV_binning = [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 23, 27, 32, 40, 55, 100]
absYV_binning = [0, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4]

# categorical axes in python bindings always have an overflow bin, so use a regular
# axis for the charge
axis_charge = hist.axis.Regular(2, -2., 2., underflow=False, overflow=False, name = "charge")

axis_passIso = hist.axis.Boolean(name = "passIso")
axis_passMT = hist.axis.Boolean(name = "passMT")

nominal_axes = [axis_eta, axis_pt, axis_charge, axis_passIso, axis_passMT]

def common_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", "--nThreads", type=int, help="number of threads")
    parser.add_argument("--debug", action='store_true', help="Debug output")
    initargs,_ = parser.parse_known_args()

    logging.basicConfig(level=logging.INFO if not initargs.debug else logging.DEBUG)

    import ROOT
    ROOT.gInterpreter.ProcessLine(".O3")
    if not initargs.nThreads:
        ROOT.ROOT.EnableImplicitMT()
    elif initargs.nThreads != 1:
        ROOT.ROOT.EnableImplicitMT(initargs.nThreads)
    import narf
    import wremnants
    from wremnants import theory_tools

    parser.add_argument("--pdfs", type=str, nargs="*", default=["nnpdf31"], choices=theory_tools.pdfMapExtended.keys(), help="PDF sets to produce error hists for")
    parser.add_argument("--altPdfOnlyCentral", action='store_true', help="Only store central value for alternate PDF sets")
    parser.add_argument("--maxFiles", type=int, help="Max number of files (per dataset)", default=-1)
    parser.add_argument("--filterProcs", type=str, nargs="*", help="Only run over processes matched by (subset) of name", default=[])
    parser.add_argument("--v8", action='store_true', help="Use NanoAODv8. Default is v9")
    parser.add_argument("-p", "--postfix", type=str, help="Postfix for output file name", default=None)
    parser.add_argument("--theory_corr", nargs="*", choices=["scetlib", "scetlibMSHT20", "scetlibHelicity", "dyturbo", "matrix_radish"], 
        help="Apply corrections from indicated generator. First will be nominal correction.", default=[])
    parser.add_argument("--theory_corr_alt_only", action='store_true', help="Save hist for correction hists but don't modify central weight")
    parser.add_argument("--skipHelicity", action='store_true', help="Skip the qcdScaleByHelicity histogram (it can be huge)")
    return parser,initargs