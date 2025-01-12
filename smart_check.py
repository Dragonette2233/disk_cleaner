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

        smart_short_view = []
        smart_complex_view = []
        # print(strings)
        for i in strings:
            i_as_l = i.split()
            if i_as_l:
                if i_as_l[0] in ('1', '4', '5', '9', '197', '198'):
                    match i_as_l[0]:
                        case '5':
                            smart_short_view.append(i_as_l[-1])
                            smart_complex_view.append(f"Relocated -- {i_as_l[-1]}")
                        case '197':
                            smart_short_view.append('p' + i_as_l[-1])
                            smart_complex_view.append(f"Current pending -- {i_as_l[-1]}")
                        case '198':
                            smart_short_view.append('u' + i_as_l[-1])
                            smart_complex_view.append(f"Offline uncorrectable -- {i_as_l[-1]}")
                        case '9':
                            smart_complex_view.insert(0, f"Power on hours -- {i_as_l[-1]}")
            
                        
        short_string = ''.join(i for i in smart_short_view)
        complex_string = '\n'.join(i for i in smart_complex_view)
   
        smarts_short.append(short_string)
        smarts_complex.append(complex_string)
    
    return [smarts_short, smarts_complex]
