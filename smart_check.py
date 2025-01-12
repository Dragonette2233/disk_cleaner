import os
import subprocess

SMART_CTL_EX = os.path.join('.', 'smartmontools', 'bin', 'smartctl.exe')


def get_short_smarts():
    # return SMART data like 0p0u0 (0 bads, 0 pendings, 0 uncorrectable)
    smarts_short = []
    smarts_complex = []
    
    for i in range(10):
        process = subprocess.Popen(
        f'"{SMART_CTL_EX}" -A /dev/pd{i}',  # Enclose the path in quotes to handle spaces
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True
        )

        stdout, _ = process.communicate()  # Use communicate() to read stdout and stderr
        strings = stdout.split('\n')

        smart_end = []
        smart_long = stdout.split("Vendor Specific SMART Attributes with Thresholds:")
        if len(smart_long) > 1:
            
            smarts_complex.append(smart_long[1])
        # print(strings)
        for i in strings:
            i_as_l = i.split()
            if i_as_l:
                if i_as_l[0] in ('1', '4', '5', '9', '197', '198'):
                    match i_as_l[0]:
                        case '5':
                            smart_end.append(i_as_l[-1])
                        case '197':
                            smart_end.append('p' + i_as_l[-1])
                        case '198':
                            smart_end.append('u' + i_as_l[-1])
            
                # print('--'.join([i_as_l[0], i_as_l[1], i_as_l[-1]]))
                        
        short_smart = ''.join(i for i in smart_end)
        
        smarts_short.append(short_smart)
    
    return [smarts_short, smarts_complex]
