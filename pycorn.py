# -*- coding: utf-8 -*-
'''
PyCORN - script to extract data from .res (results) files generated 
by UNICORN Chromatography software supplied with ÄKTA Systems
(c)2014 - Yasar L. Ahmed
v0.11
'''

import struct
import argparse
import codecs
import os
import time

start = time.time()

parser = argparse.ArgumentParser(
    description = "Extract data from UNICORN .res files to .csv/.txt and plot them (matplotlib required)",
    epilog = "Make it so!")
parser.add_argument("-c", "--check", 
                    help = "Perform simple check if file is supported",
                    action = "store_true")
parser.add_argument("-n", "--info", 
                    help = "Display entries in header",
                    action = "store_true")
parser.add_argument("-i", "--inject", type = int, default = 0, 
                    help = "Set injection number # as zero retention, use -t to find injection points",
                    metavar="#")
parser.add_argument("-t", "--points", 
                    help = "Display injection points",
                    action = "store_true")
parser.add_argument("-e", "--extract", 
                    help = "Extract supported data blocks",
                    action = "store_true")
parser.add_argument("-p", "--plot", 
                    help = 'Plot curves',
                    action = "store_true")
parser.add_argument("-f", "--format", type = str,
                    choices=['svg','svgz','tif','tiff','jpg','jpeg','png','ps','eps','raw','rgba','pdf','pgf'],
                    default = 'pdf',
                    help = "File format of plot files (default: pdf)")
parser.add_argument("-u", "--user", 
                    help = "Show stored user name",
                    action = "store_true")
parser.add_argument("inp_res",
                    help = "Input .res file",
                    metavar = "<file>.res",
                    type = argparse.FileType('rb'))

args = parser.parse_args()
file_in = args.inp_res.name # file handling is not done by argparse
file_base = args.inp_res.name[:-4]
args.inp_res.close() # see comment above

'''
Magic numbers
'''
RES_magic_id = b'\x11\x47\x11\x47\x18\x00\x00\x00\xB0\x02\x00\x00\x20\x6C\x03\x00'
CNotes_id = b'\x00\x00\x01\x00\x02\x00\x03\x22'
Methods_id = b'\x00\x00\x01\x00\x02\x00\x01\x02'
Logbook_id = b'\x00\x00\x01\x00\x04\x00\x48\x04'
SensData_id = b'\x00\x00\x01\x00\x04\x00\x01\x14'
Fractions_id = b'\x00\x00\x01\x00\x04\x00\x44\x04'
Inject_id = b'\x00\x00\x01\x00\x04\x00\x46\x04'
LogBook_id = b'\x00\x00\x01\x00\x02\x00\x01\x13' #capital B!

inj_sel = 0.0   #injection point is by default 0.0 ml


def input_check(inp):
    '''
    Checks if input file is a supported res file
    x = magic number, y = version string, z = file size/EOF
    '''
    print((" ---- \n Input file: {0}").format(inp))
    with open(inp, 'rb') as fo:
        file_read = fo.read()
        x=file_read.find(RES_magic_id, 0, 16)
        y=file_read.find(b'UNICORN 3.10',16,36)
        z=struct.unpack("i", file_read[16:20])
    if (x,y) == (0,24):
        print(" Input is UNICORN 3.10 file!")
        x,y = (0,0)
    else:
        print(" Input is not UNICORN 3.10 file!")
        x,y = (1,1)
    if z[0] == os.path.getsize(file_in):
        print(" File size check - OK")
        z = 0
    else:
        print(" File size mismatch - file corrupted?")
        z = 1
    if (x,y,z) != (0,0,0):
        print("\n File not supported - stop!")
        return False
    else:
        print("\n Alles safe! - Go go go!")
        return True


def readheader(inp):
    '''
    Extracts all the entries/declarations in the header (starts at position 686)
    '''
    tmp_list = []
    with open(inp, 'rb') as fo:
        fread = fo.read()
        header_end = fread.find(LogBook_id) + 342
        for i in range(686,header_end, 344):
            decl = struct.unpack("8s296s4i", fread[i:i+320])
            full_label = codecs.decode(decl[1], 'cp1252').rstrip("\x00")
            if full_label.find(':') == -1:
                r_name = ''
                d_name = full_label
            else:
                r_name = full_label[:full_label.find(':')]
                d_name = full_label[full_label.find('_')+1:]
            x = dict(magic_id = decl[0],
                     run_name = r_name,
                     data_name = d_name,
                     d_size = decl[2],
                     off_next = decl[3],
                     adresse = decl[4],
                     off_data = decl[5],
                     d_start = decl[4] + decl[5],
                     d_end = decl[4] + decl[2])
            tmp_list.append(x)
    return(tmp_list)


def showheader(inp,full="true"):
    '''
    Prints content of header
    '''
    header = readheader(file_in)
    print((" ---- \n Header of {0}: \n").format(inp))
    if full == "true":
        print("  MAGIC_ID, ENTRY_NAME, BLOCK_SIZE, OFFSET_TO_NEXT, ADRESSE, OFFSET_TO_DATA")
    else:
        print(" ENTRY_NAME, BLOCK_SIZE, OFFSET_TO_NEXT, ADRESSE, OFFSET_TO_DATA")
    for i in header:
        if full == "true":
            print(" ", i['magic_id'],i['data_name'],i['d_size'],i['off_next'],i['adresse'],i['off_data'])
        else:
            print("",i['data_name'], i['d_size'], i['off_next'], i['adresse'], i['off_data'])


def showuser(inp):
    '''
    Show stored user name
    '''
    with open(inp, 'rb') as fo:
        fread = fo.read(512)
        u = struct.unpack("40s", fread[118:158])
        dec_u = codecs.decode(u[0], 'cp1252').rstrip("\x00")
        print((" ---- \n User: {0}").format(dec_u))


def dataextractor(inp):
    '''
    Identify data type by comparing magic id, then run appropriate
    function to extract data, update orig. dict to include new data
    '''
    if inp['d_size'] == 0:
        pass
    elif inp['magic_id'] == CNotes_id or inp['magic_id'] == Methods_id:
        inp.update(data=meta2_read(inp))
        return inp
    elif inp['magic_id'] == Logbook_id or inp['magic_id'] == Inject_id or inp['magic_id'] == Fractions_id:
        inp.update(data=meta1_read(inp))
        return inp
    elif inp['magic_id'] == SensData_id:
        values,unit=sensor_read(inp)
        inp.update(data=values, unit=unit)
        return inp
    else:
        pass


def meta1_read(inp, silent="false"):
    '''
    Extracts meta-data/type1, Logbook, fractions and Inject marks
    '''
    if silent == "true":
        pass
    else:
        print((" Extracting: {0}").format(inp['data_name']))
    finaldata = []
    with open(file_in, 'rb') as fo:
        fread = fo.read()
        for i in range(inp['d_start'], inp['d_end'], 180):
            dp = struct.unpack("dd158s", fread[i:i+174])
            #acc_time = dp[0] # not used atm
            acc_volume = round(dp[1]-inj_sel,4)
            label = (codecs.decode(dp[2], 'cp1250')).rstrip('\x00')
            merged_data=acc_volume,label
            finaldata.append(merged_data)
    return(finaldata)


def meta2_read(inp):
    '''
    Extracts meta-data/type2, Method/Program used in the run
    '''
    print((" Extracting: {0}").format(inp['data_name']))
    with open(file_in,'rb') as fo:
        fo.seek(inp['d_start'])
        tmp_data = fo.read(inp['d_size'])
        size = tmp_data.rfind(b'\n') #declared block-size in header is always off
        fo.seek(inp['d_start'])        #by a few bytes, hence it is redetermined here
        data = fo.read(size)
    return(data)


def sensor_read(inp):
    '''
    extracts sensor/run-data and applies correct division
    '''
    tmp_list0 = []
    if "UV" in inp['data_name'] or "Cond" == inp['data_name'] or "Flow" == inp['data_name']:
        sensor_div = 1000.0
    elif "Pressure" in inp['data_name']:
        sensor_div = 100.0
    else:
        sensor_div = 10.0
    print((" Extracting: {0}").format(inp['data_name']))
    with open(file_in, 'rb') as fo:
        fread = fo.read()
        for i in range(inp['adresse']+207, inp['adresse']+222, 15):
            s_unit = struct.unpack("15s", fread[i:i+15])
            s_unit_dec = (codecs.decode(s_unit[0], 'cp1252')).rstrip('\x00')
        for i in range(inp['d_start'], inp['d_end'], 8):
            sread = struct.unpack("ii", fread[i:i+8])
            data=round((sread[0]/100.0)-inj_sel,4),sread[1]/sensor_div
            tmp_list0.append(data)
    return(tmp_list0,s_unit_dec)


def inject_det(inp,show="false"):
    '''
    Finds injection points - required for adjusting retention
    '''
    injection_points = []
    header = readheader(inp)
    for i in header:
        if i['magic_id'] == Inject_id:
            injection = meta1_read(i,silent="true")[0][0]
            injection_points.append(injection)
            if injection != 0.0:
                injection_points.insert(0,0.0)
    if injection_points == []:
        injection_points = [0.0]
        if show == "true":
            print((" ---- \n Injection points: \n # \t ml \n 0 \t {0}").format(injection_points[0]))
        return(injection_points)
    else:
        if show == "true":
            print(" ---- \n Injection points: \n # \t ml")
            for x,y in enumerate(injection_points):
                print((" {0} \t {1}").format(x,y))
        return(injection_points)


def store_in_list(inp):
    '''
    extract all data and store in list
    '''
    global inj_sel
    inj_sel = inject_det(file_in,show="false")[args.inject]
    header = readheader(inp)
    for i in header:
        x = dataextractor(i)
        if x == None:
            pass
        else:
            data_storage.append(x)


def writer(inp):
    '''
    general writer, picks the correct writer function based on data type
    '''
    if inp['magic_id'] == Methods_id or inp['magic_id'] == CNotes_id:
        meta_writer(inp)
    else:
        data_writer(inp)


def meta_writer(inp):
    '''
    writes meta-data to txt-files
    '''
    ext = "_"+inp['data_name']+".txt"
    unicode_data = codecs.decode(inp['data'], 'cp1250')
    content = unicode_data.encode('utf-8')
    with open(file_base+ext,'wb') as fout:
        print((" Writing {0}").format(inp['data_name']))
        fout.write(inp['data'])

             
def data_writer(inp):
    '''
    writes sensor/run-data to csv-files
    '''
    fname = file_base+"_"+inp['run_name']+"_"+inp['data_name']+".csv"
    if "Logbook" in inp['data_name']:
        pass
    else:
        with open(fname, 'wb') as fout:
            print((" Writing {0}").format(inp['data_name']))
            for i in inp['data']:
                dp = (str(i[0]) + "," + str(i[1]) + str("\n")).encode('utf-8')
                fout.write(dp)

def mapper(min_val,max_val,perc):
    '''
    calculate relative position in delta min/max
    '''
    x = abs(max_val-min_val)*perc
    if min_val < 0:
        return(x - abs(min_val))
    else:
        return(x + min_val)


def expander(min_val,max_val,perc):
    '''
    expand -/+ direction of two values by a percentage of their delta
    '''
    delta = abs(max_val-min_val)
    x = delta*perc 
    return(min_val - x, max_val + x)

def plotter(inp,fractions):
    x_val = [x[0] for x in inp['data']]
    y_val = [x[1] for x in inp['data']]
    if fractions == None:
        plot_x_min = x_val[0]
        plot_x_max = x_val[-1]
    else:
        plot_x_min = fractions[0][0]
        plot_x_max = fractions[-1][0]
    plot_y_min = expander(min(y_val),max(y_val),0.04)[0]
    plot_y_max = expander(min(y_val),max(y_val),0.04)[1]
    ax = plt.gca()
    if type(y_val[0]) == float or type(y_val[0]) == int:
        plt.xlim(xmin = plot_x_min, xmax = plot_x_max)
        plt.ylim(ymin = plot_y_min, ymax = plot_y_max)
        frac_y_pos = mapper(ax.get_ylim()[0],ax.get_ylim()[1],0.02)
        plt.title(file_in + " - " + inp['run_name'] + " - " + inp['data_name'], size=12)
        plt.ylabel(inp['unit'])
        plt.xlabel('ml')
        ax.spines['right'].set_color('none')
        ax.spines['top'].set_color('none')
        plt.tick_params(axis='x',direction='out',top='off')
        plt.tick_params(axis='y',direction='out',right='off')
        plt.plot(x_val, y_val,linewidth=1.5, color='b')
        if fractions != None:
            frac_x = [x[0] for x in fractions]
            frac_tmp = frac_x[1:]
            frac_tmp.append(0)
            frac_delta = [abs(a - b) for a,b in zip(frac_tmp,frac_x)]
            for i in fractions:
                plt.axvline(x=i[0], ymin=0.065, ymax=0.0,color='r', linewidth=0.85)
                plt.annotate(i[1], xy=(i[0]+frac_delta[fractions.index(i)]*0.1,frac_y_pos), verticalalignment='bottom', size=8, rotation=90)
        print(" Plotting " + inp['data_name'])
        ext = "." + (args.format)[-3:]
        file_name = file_base + "_Plot_" + inp['run_name'] + "_" + inp['data_name'] + ext
        plt.savefig(file_name, papertype='a4',dpi=300)
        plt.clf()


def endscript():
    print(" Plotting canceled")
    exit

#--- run time---#

if args.user:
    showuser(file_in)
    
if args.check:
    input_check(file_in)
    
if args.info:
    showheader(file_in,full="false")
    
if args.points:
    inject_det(file_in,show="true")
    
if args.plot:
    if input_check(file_in) == True:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("\n Matplotlib not found - Plotting will not work!\n")
            endscript()
        else:
            print("\n Matplotlib found - WARNING - PLOTTING IS EXPERIMENTAL\n")
            data_storage = []
            store_in_list(file_in)
            magic_ids = [x['magic_id'] for x in data_storage]
            if Fractions_id in magic_ids:
                fraction_idx = magic_ids.index(Fractions_id)
                fractions = data_storage[fraction_idx]['data']
            else:
                fractions = None
            for i in data_storage:
                if i['magic_id'] == SensData_id:
                    plotter(i,fractions)
    else:
        pass

if args.extract:
    if input_check(file_in) == True:
        data_storage = []
        store_in_list(file_in)
        for i in data_storage:
            writer(i)
    else:
        pass

end = time.time()
runtime = str(end - start)
print("\n ----")
print((" Runtime: {0} seconds!").format(runtime[:5]))