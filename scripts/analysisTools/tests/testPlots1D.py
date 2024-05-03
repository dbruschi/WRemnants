#!/usr/bin/env python3

from wremnants.datasets.datagroups import Datagroups
from wremnants import histselections as sel
#from wremnants import plot_tools,theory_tools,syst_tools
from utilities import boostHistHelpers as hh,common, logging

import narf
import wremnants
from wremnants import theory_tools,syst_tools,theory_corrections
import hist

import numpy as np
from utilities.io_tools import input_tools

import lz4.frame

import argparse
import os
import shutil
import logging
import re

## safe batch mode
import sys
args = sys.argv[:]
sys.argv = ['-b']
import ROOT
sys.argv = args
ROOT.gROOT.SetBatch(True)
ROOT.PyConfig.IgnoreCommandLineOptions = True

from copy import *

from scripts.analysisTools.plotUtils.utility import *

sys.path.append(os.getcwd())
from scripts.analysisTools.tests.cropNegativeTemplateBins import cropNegativeContent

def plotDistribution2D(args, groups, datasets, histname, outdir, canvas2Dshapes=None,
                       xAxisName="x axis", yAxisName="y axis", zAxisName="Events",
                       scaleToUnitArea=False):
    
    groups.setNominalName(histname)
    groups.loadHistsForDatagroups(histname, syst="", procsToRead=datasets)
    histInfo = groups.getDatagroups()
    rootHists = {}
    
    for d in datasets:
        hnarf = histInfo[d].hists[histname]
        rootHists[d] = narf.hist_to_root(hnarf)
        rootHists[d].SetName(f"{histname}_{d}")
        rootHists[d].SetTitle(f"{d}")

        drawCorrelationPlot(rootHists[d], xAxisName, yAxisName, zAxisName,
                            f"{rootHists[d].GetName()}", plotLabel="ForceTitle", outdir=outdir,
                            smoothPlot=False, drawProfileX=False, scaleToUnitArea=scaleToUnitArea,
                            draw_both0_noLog1_onlyLog2=1, passCanvas=canvas2Dshapes)

def plotDistribution1D(hdata, hmc, datasets, outfolder_dataMC, canvas1Dshapes=None,
                       xAxisName="variable", plotName="variable_failIso_jetInclusive",
                       draw_both0_noLog1_onlyLog2=1, ratioPadYaxisTitle="Data/pred::0.9,1.1",
                       scaleToUnitArea=False, noRatioPanel=False):
    
    createPlotDirAndCopyPhp(outfolder_dataMC)
    if not canvas1Dshapes:
        canvas1Dshapes = ROOT.TCanvas("canvas1Dshapes","",700,800)

    nColumns = 3
    legendLowX = 0.82 if len(hmc) < nColumns else 0.72
    legend = ROOT.TLegend(0.2,nColumns,0.95,0.92)
    legend.SetFillColor(0)
    legend.SetFillStyle(0)
    legend.SetBorderSize(0)
    legend.SetNColumns(nColumns)

    stackIntegral = 0.0
    for d in datasets:
        if d == "Data":
            legend.AddEntry(hdata, "Data", "EP")
        else:
            cropNegativeContent(hmc[d])
            hmc[d].SetFillColor(colors_plots_[d])
            hmc[d].SetLineColor(ROOT.kBlack)
            hmc[d].SetMarkerSize(0)
            hmc[d].SetMarkerStyle(0)
            stackIntegral += hmc[d].Integral()

    if scaleToUnitArea:
        hdata.Scale(1.0/hdata.Integral())

    stack_1D = ROOT.THStack("stack_1D", "signal and backgrounds")
    hmcSortedKeys = sorted(hmc.keys(), key= lambda x: hmc[x].Integral())
    for i in hmcSortedKeys:
        if scaleToUnitArea:
            hmc[i].Scale(1.0/stackIntegral)
        stack_1D.Add(hmc[i])
    # reverse sorting for legend, first the ones with larger integral
    for i in list(reversed(hmcSortedKeys)):
        legend.AddEntry(hmc[i], legEntries_plots_[i], "LF")

    drawTH1dataMCstack(hdata, stack_1D, xAxisName, "Fraction of events" if scaleToUnitArea else "Events", plotName,
                       outfolder_dataMC, legend, ratioPadYaxisNameTmp=ratioPadYaxisTitle, passCanvas=canvas1Dshapes,
                       lumi="16.8", drawLumiLatex=True, xcmsText=0.3, noLegendRatio=True,
                       draw_both0_noLog1_onlyLog2=draw_both0_noLog1_onlyLog2, noRatioPanel=noRatioPanel)

if __name__ == "__main__":

    parser = common_plot_parser()
    parser.add_argument("inputfile", type=str, nargs=1)
    parser.add_argument("outputfolder",   type=str, nargs=1)
    parser.add_argument('-p','--processes', default=None, nargs='*', type=str,
                        help='Choose what processes to plot, otherwise all are done')
    parser.add_argument('--plot', nargs='+', type=str,
                        help='Choose what distribution to plot by name')
    parser.add_argument("-x", "--xAxisName", nargs='+', type=str, help="x axis name")
    parser.add_argument("-r", "--ratioRange", nargs=2, type=float, default=[0.9,1.1], help="Min and max of ratio range")
    parser.add_argument(     '--plot2D', action='store_true',   help='To plot 2D histograms and 1D projections')
    parser.add_argument("-y", "--yAxisName", nargs='+', type=str, help="y axis name (only for 2D plots)")
    parser.add_argument("-l", "--lumi", type=float, default=None, help="Normalization for 2D plots (if the input does not have data the luminosity is set to 1/fb)")
    parser.add_argument(     '--normUnitArea', action='store_true',   help='Scale histogram to unit area')
    args = parser.parse_args()
    
    logger = logging.setup_logger(os.path.basename(__file__), args.verbose)
    
    fname = args.inputfile[0]
    outdir_original = args.outputfolder[0]
    outdir = createPlotDirAndCopyPhp(outdir_original, eoscp=args.eoscp)
        
    ROOT.TH1.SetDefaultSumw2()

    adjustSettings_CMS_lumi()
    canvas1D = ROOT.TCanvas("canvas1D", "", 800, 900)
    canvas2D = ROOT.TCanvas("canvas2D", "", 900, 800)

    groups = Datagroups(fname)
    if args.lumi:
        groups.lumi = args.lumi
        logger.warning(f"Renormalizing MC to {args.lumi}/fb")
    datasets = groups.getNames()
    if args.processes is not None and len(args.processes):
        datasets = list(filter(lambda x: x in args.processes, datasets))
    logger.info(f"Will plot datasets {datasets}")

    if args.plot2D:
        for ip,p in enumerate(args.plot):
            xAxisName=args.xAxisName[ip]
            yAxisName=args.yAxisName[ip]
            plotDistribution2D(args, groups, datasets, p, outdir, canvas2D, xAxisName, yAxisName, scaleToUnitArea=args.normUnitArea)
        copyOutputToEos(outdir_original, eoscp=args.eoscp)
        quit()

    ratioMin = args.ratioRange[0]
    ratioMax = args.ratioRange[1]
    ratioPadYaxisTitle=f"Data/pred::{ratioMin},{ratioMax}"

    for ip,p in enumerate(args.plot):

        groups.setNominalName(p)
        groups.loadHistsForDatagroups(p, syst="", procsToRead=datasets)

        histInfo = groups.getDatagroups()
        rootHists = {}
        
        for d in datasets:
            hnarf = histInfo[d].hists[p]
            rootHists[d] = narf.hist_to_root(hnarf)
            rootHists[d].SetName(f"{p}_{d}")

        hdata = rootHists["Data"] if "Data" in rootHists.keys() else copy.deepcopy(rootHists[datasets[0]].Clone("dummyData"))
        hmc = {d : rootHists[d] for d in datasets if d != "Data"}
        plotDistribution1D(hdata, hmc, datasets, outdir, canvas1Dshapes=canvas1D,
                           xAxisName=args.xAxisName[ip], plotName=p, ratioPadYaxisTitle=ratioPadYaxisTitle, scaleToUnitArea=args.normUnitArea,
                           noRatioPanel="Data" not in rootHists.keys())

    copyOutputToEos(outdir_original, eoscp=args.eoscp)
