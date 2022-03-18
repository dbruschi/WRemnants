import ROOT
import hist
import numpy as np

ROOT.gInterpreter.Declare('#include "theoryTools.h"')

# integer axis for -1 through 7
axis_helicity = hist.axis.Integer(
    -1, 8, name="helicity", overflow=False, underflow=False
)

# this puts the bin centers at 0.5, 1.0, 2.0
axis_muRfact = hist.axis.Variable(
    [0.25, 0.75, 1.25, 2.75], name="muRfact", underflow=False, overflow=False
)
axis_muFfact = hist.axis.Variable(
    [0.25, 0.75, 1.25, 2.75], name="muFfact", underflow=False, overflow=False
)

scale_tensor_axes = (axis_muRfact, axis_muFfact)

pdfMap = {"nnpdf31" : {
            "name" : "pdfNNPDF31",
            "branch" : "LHEPdfWeight",
            },
        }

def define_prefsr_vars(df):
    df = df.Define("prefsrLeps", "wrem::prefsrLeptons(GenPart_status, GenPart_statusFlags, GenPart_pdgId, GenPart_genPartIdxMother)")
    df = df.Define("genl", "ROOT::Math::PtEtaPhiMVector(GenPart_pt[prefsrLeps[0]], GenPart_eta[prefsrLeps[0]], GenPart_phi[prefsrLeps[0]], GenPart_mass[prefsrLeps[0]])")
    df = df.Define("genlanti", "ROOT::Math::PtEtaPhiMVector(GenPart_pt[prefsrLeps[1]], GenPart_eta[prefsrLeps[1]], GenPart_phi[prefsrLeps[1]], GenPart_mass[prefsrLeps[1]])")
    df = df.Define("genV", "ROOT::Math::PxPyPzEVector(genl)+ROOT::Math::PxPyPzEVector(genlanti)")
    df = df.Define("ptVgen", "genV.pt()")
    df = df.Define("massVgen", "genV.mass()")
    df = df.Define("yVgen", "genV.Rapidity()")
    df = df.Define("absYVgen", "std::fabs(yVgen)")
    df = df.Define("chargeVgen", "GenPart_pdgId[prefsrLeps[0]] + GenPart_pdgId[prefsrLeps[1]]")
    df = df.Define("csSineCosThetaPhi", "wrem::csSineCosThetaPhi(genl, genlanti)")
    return df

def define_scale_tensor(df):
    # convert vector of scale weights to 3x3 tensor and clip weights to |weight|<10.
    df = df.Define("scaleWeights_tensor", "wrem::makeScaleTensor(LHEScaleWeight, 10.);")
    df = df.Define("scaleWeights_tensor_wnom", "auto res = scaleWeights_tensor; res = nominal_weight*res; return res;")

    return df

def define_and_apply_scetlib_corr(df, weight_expr):
    df = df.Define("nominal_weight_uncorr", weight_expr)
    df = df.Define("scetlibWeight_tensor", scetlibCorr_helper, ["chargeVgen", "massVgen", "yVgen", "ptVgen", "nominal_weight_uncorr"])
    scetlibUnc = df.HistoBoost("scetlibUnc", nominal_axes, [*nominal_cols, "scetlibWeight_tensor"], tensor_axes=scetlibCorr_helper.tensor_axes)
    df = df.Define("nominal_weight", "scetlibWeight_tensor(0)")
    nominal_uncorr = df.HistoBoost("nominal_uncorr", nominal_axes, [*nominal_cols, "nominal_weight_uncorr"])
    return (nominal_uncorr, scetlibUnc)

def moments_to_angular_coeffs(hist_moments_scales):
    s = hist.tag.Slicer()

    # select constant term, leaving dummy axis for broadcasting
    hist_moments_scales_m1 = hist_moments_scales[{"helicity" : s[-1j:-1j+1]}]

    vals = hist_moments_scales_m1.values(flow=True)

    # replace zero values to avoid warnings
    norm_vals = np.where( vals==0., 1., vals)

    # e.g. from arxiv:1708.00008 eq. 2.13
    offsets = np.array([0., 4., 0., 0., 0., 0., 0., 0., 0.])
    scales = np.array([1., -10., 5., 10., 4., 4., 5., 5., 4.])

    # for broadcasting
    hel_ax_idx = list(hist_moments_scales.axes).index(hist_moments_scales.axes["helicity"])
    ntrailing_ax = hist_moments_scales.ndim - hel_ax_idx - 1
    if ntrailing_ax:
        new_axes = tuple(range(offsets.ndim, offsets.ndim+ntrailing_ax))
        offsets = np.expand_dims(offsets, axis=new_axes)
        scales = np.expand_dims(scales, axis=new_axes)

    view = hist_moments_scales.view(flow=True)

    coeffs = scales*view / norm_vals + offsets

    # replace values in zero-xsec regions (otherwise A0 is spuriously set to 4.0 from offset)
    coeffs = np.where(vals == 0., 0.*view, coeffs)

    hist_coeffs_scales = hist.Hist(*hist_moments_scales.axes, storage = hist_moments_scales._storage_type(), name = "hist_coeffs_scales",
        data = coeffs
    )


    return hist_coeffs_scales

def qcdByHelicityLabels():
    coeffs = ["const"]+[f"a{i}" for i in range(8)]
    scaleVars = ["muRmuF", "muR", "muF"]
    return  [f"{var}_{coeff}{t}" for var in scaleVars for t in ["Up", "Down"] for coeff in coeffs]

def qcdScaleNames():
    # Exclude central and extreme variations
    shifts = ["muRmuFDown", "muRDown", "", "muFDown", "", "muFUp", "muRUp", "", "muRmuFUp"]
    return ["_".join(["QCDscale", s]) if s != "" else s for s in shifts]

def massWeightNames(matches=None, wlike=False):
    central=10
    nweights=21
    names = [f"massShift{int(abs(central-i)*10)}MeV{'Down' if i < central else 'Up'}" for i in range(nweights)]
    if wlike:
        # These are the Z width variations
        names.extend(["", ""])
    # If name is "" it won't be stored
    return [x if not matches or any(y in x for y in matches) else "" for x in names]

def pdfNames(cardTool, pdf, skipFirst=True):
    size = 101
    names = cardTool.mirrorNames(f"pdf{{i}}{pdf}", size)
    if skipFirst:
        names[0] = ""
        names[size] = ""
    # TODO: This is probably not needed anymore, check with low PU
    if False and pdf == "NNPDF31":
        names[size-2] = "pdfAlphas002Up"
        names[size-1] = "pdfAlphas002Down"
        # Drop the mirrored alphaS variations
        names[size*2-2] = ""
        names[size*2-1] = ""
    return names

