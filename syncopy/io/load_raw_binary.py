# -*- coding: utf-8 -*-
#
# Read binary files from disk
# 
# Created: 2019-01-22 09:13:56
# Last modified by: Stefan Fuertinger [stefan.fuertinger@esi-frankfurt.de]
# Last modification time: <2019-03-20 11:31:14>

# Builtin/3rd party package imports
import os
import sys
import numpy as np

# Local imports
from syncopy.utils import io_parser, data_parser, SPYIOError, SPYTypeError, SPYValueError
from syncopy.datatype import AnalogData
from syncopy.datatype.base_data import VirtualData
import syncopy.datatype as swd

__all__ = ["load_binary_esi", "read_binary_esi_header"]

##########################################################################################
def load_binary_esi(filename,
                    channel="channel",
                    unit="unit",
                    event="event",
                    trialdefinition=None,
                    out=None):
    """
    Docstring
    """

    # Convert input to list (if it is not already) - parsing is performed
    # by ``read_binary_esi_header`` below
    if not isinstance(filename, (list, np.ndarray)):
        filename = [filename]

    # Read headers of provided file(s) to see what we're dealing with here
    headers = []
    tsample = []
    filename = [os.path.abspath(fname) for fname in filename]
    for fname in filename:
        hdr = read_binary_esi_header(fname)
        hdr["file"] = fname
        headers.append(hdr)
        tsample.append(hdr["tSample"])

    # Make sure we're not mixing file-types
    exts = [os.path.splitext(fname)[1] for fname in filename]
    if not set(exts).issubset([".lfp", ".mua"]) and np.unique(exts).size > 1:
        lgl = "files of identical type"
        act = "{}-files".format("".join(ext + ", " for ext in exts)[:-2])
        raise SPYValueError(legal=lgl, actual=act, varname="filename")

    # In case of spike data, we only support reading single ".spk" files
    if exts[0] == ".spk" and len(exts) > 1:
        lgl = "single .spk file"
        act = "{} .spk files".format(str(len(exts)))
        raise SPYValueError(legal=lgl, varname="filename", actual=act)

    # FIXME: does this make sense for every type of data?
    # Abort, if files have differing sampling times
    if not np.array_equal(tsample, [tsample[0]]*len(tsample)):
        raise SPYValueError(legal="identical sampling interval per file")

    # Depending on file-extension, we either deal with LFP/MUA or Spike/Event data
    if exts[0] == ".spk":
        dclass = "SpikeData"
    elif exts[0] in [".lfp", ".mua"]:
        dclass = "AnalogData"
    else:
        raise NotImplementedError("Cannot handle {}-files atm".format(exts[0]))

    # Make sure `out` does not contain unpleasant surprises (if provided)
    new_out = True
    if out is not None:
        try:
            data_parser(out, varname="out", writable=True, dataclass=dclass)
        except Exception as exc:
            raise exc
        new_out = False
    else:
        out = getattr(swd, dclass)()
        new_out = True

    # Deal with MUA/LFP data
    if dclass == "AnalogData":

        # Open each file as memmap
        dsets = []
        for fk, fname in enumerate(filename):
            dsets.append(np.memmap(fname, offset=int(headers[fk]["length"]),
                                   mode="r", dtype=headers[fk]["dtype"],
                                   shape=(headers[fk]["M"], headers[fk]["N"])))

        # Instantiate VirtualData class w/ constructed memmaps (error checking is done in there)
        data = VirtualData(dsets)

        # First things first: attach data to output object
        out.data = data

        # If necessary, construct list of channel labels (parsing is done by setter)
        if isinstance(channel, str):
            channel = [channel + str(i + 1) for i in range(data.M)]

        # Set remaining attributes
        out.channel = np.array(channel)

    elif dclass == "SpikeData":

        # Open provided data-file as memmap and attach it to `out`
        out.data = np.memmap(filename[0], offset=int(headers[0]["length"]),
                             mode="r", dtype=headers[0]["dtype"],
                             shape=(headers[0]["M"], headers[0]["N"]))

        # If necessary, construct lists for channel and unit labels
        if isinstance(channel, str):
            nchan = np.unique(out.data[:, out.dimord.index("channel")]).size
            channel = [channel + str(i + 1) for i in range(nchan)]
        if isinstance(unit, str):
            nunit = np.unique(out.data[:, out.dimord.index("unit")]).size
            unit = [unit + str(i + 1) for i in range(nunit)]

        # Set meta-data
        out.channel = channel
        out.unit = unit

    # Attach file-header and detected samplerate
    out._hdr = headers
    out.samplerate = float(1/headers[0]["tSample"]*1e9)

    # Now we can abuse ``redefinetrial`` to set trial-related props
    out.redefinetrial(trialdefinition)

    # Write `cfg` entries
    out.cfg = {"method" : sys._getframe().f_code.co_name,
               "hdr" : headers}

    # Write log entry
    log = "loaded data:\n" +\
          "\tfile(s) = {fls:s}"
    out.log = log.format(fls="\n\t\t  ".join(fl for fl in filename))

    # Happy breakdown
    return out if new_out else None

##########################################################################################
def read_binary_esi_header(filename):
    """
    Docstring
    """

    # SyNCoPy raw binary dtype-codes
    dtype = {
        1 : 'int8',
        2 : 'uint8', 
        3 : 'int16', 
        4 : 'uint16', 
        5 : 'int32', 
        6 : 'uint32', 
        7 : 'int64', 
        8 : 'uint64', 
        9 : 'float32',
        10 : 'float64'
    }

    # First and foremost, make sure input arguments make sense
    try:
        io_parser(filename, varname="filename", isfile=True, exists=True,
                  ext=[".lfp", ".mua", ".evt", ".dpd", 
                       ".apd", ".eye", ".pup", ".spk"])
    except Exception as exc:
        raise exc

    # Try to access file on disk, abort if this goes wrong
    try:
        fid = open(filename, "r")
    except:
        raise SPYIOError(filename)

    # Extract file header
    hdr = {}
    hdr["version"] = np.fromfile(fid,dtype='uint8',count=1)[0]
    hdr["length"] = np.fromfile(fid,dtype='uint16',count=1)[0]
    hdr["dtype"] = dtype[np.fromfile(fid,dtype='uint8',count=1)[0]]
    if os.path.splitext(filename)[1] in [".lfp", ".mua"]:
        hdr["N"] = np.fromfile(fid,dtype='uint64',count=1)[0]
        hdr["M"] = np.fromfile(fid,dtype='uint64',count=1)[0]
    else:
        hdr["M"] = np.fromfile(fid,dtype='uint64',count=1)[0]
        hdr["N"] = np.fromfile(fid,dtype='uint64',count=1)[0]
    hdr["tSample"] = np.fromfile(fid,dtype='uint64',count=1)[0]
    fid.close()

    return hdr
    