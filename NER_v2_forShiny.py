#### select a scispacy model 
import scispacy
import spacy
from scispacy.abbreviation import AbbreviationDetector
from scispacy.umls_linking import UmlsEntityLinker

## read in files 
from pathlib import Path
import os
import docx
import re
from nltk.corpus import stopwords

from spacy import displacy
import numpy as np
import pandas as pd
from collections import defaultdict, Counter

import scispacy
import spacy
from scispacy.abbreviation import AbbreviationDetector
from scispacy.umls_linking import UmlsEntityLinker

import textract
import win32com.client
import time

import sys
sys.path.insert(0, '.\\sample_notes')
from negationDetection import negate_sequence
from body_part_dictionaries import *
from common_helper_funcs_bodyparts import *

#### Claims Reports summarization
sys.path.insert(0, '.\\Text_Summerizer\\Best_approach')
from document_summarization import *

### load in the Medical Diagnostic Procedures and Tests terms 
medical_procs = ['Angiography',
 'Angioplasty',
 'Anteroposterior','Arthroscopy',
 'AST','Basic Metabolic Panel', ## 'CC',
 'C Difficile',
 'Cellulitis','Cesarean Section', 'C Section', 'Chlamydia',
 'Cholecystectomy',
 'Colonoscopy','Comprehensive Metabolic Panel', 
 'Coronary Bypass',
 'Coronary Catheterization',
 'CPK', 'CT Scan',
 'Cystocele',
 'Debride',
 'Diagnostic X-Ray',
 'Duodenum',
 'Edema', 'EEG', 
 'angiogram', 'echocardiogram', 'nuclear bone scan',
 'Embolism',
 'Endarterectomy',
 'Endometrium',
 'Endoscopic',
 'Enterocele',
 'Esophageal Sphincter', 'Fallopian Tubes','Fluoroscopy','Gastroenterostomy',
 'GC PCR',
 ## 'GI',
 'Glucose Test',
 'Glycated Hemoglobin Test', 'Hgb A1C','Hysterectomy',
 'Image Post-Processing','Internal Fixation',
 'Ionized Calcium Test',
 'Mammogram',
 'Mammography',
 'Mastectomy',
 'MCC',
 'Meniscus',
 'Microalbumin Test',
 'Mono Test',
 'MRA', 
 'Magnetic Resonance Angiogram',
 'MRI', 
 'Magnetic Resonance Imaging',
 'Nasal Septum',
 'Natriuretic Peptide/Brain Natriuretic Peptide (BNP) Test',
 'Obstetric Panel',
 'Occult Blood Screen', 'PCR', 'PET', 'PET Scan', 'PET Scans',
 'Phosphorous',
 'Pleurisy', 'Prosthesis',
 'Protime', 
 'INR',
 'PSA',
 'PTT','TSH',
 'Ultrasound',
 'Umbilical',
 'Urinalysis',
 'Urine Pregnancy Test', 'X-Ray',  
                'CAT Scan', 'Ductogram', 'Tomosynthesis', 'Biopsy', 'Chemoembolization', 'Radioembolization', 
               'UFE', 'Uterine fibroid embolization', 'Bone density scan', 
               ## 'Cardiac PET viability', 'Cardiac SPECT perfusion'
               'SPECT', 'X-Rays', 'xray', 'xrays',
               'MRIs', 'MRAs', 'FMRIs', 'CT Scans', 'CT', 
               'surgery', 'surgeries']
medical_procs = [i.lower() for i in medical_procs]


## negation_list = []
def negation_detection(tagged_body_parts_counter, tagged_body_parts, cur_text):
    #### Multiple body parts tagged, and has essential body parts:
    if len(tagged_body_parts_counter.keys()) == 1:
        pass
    
    ## !! 2019-09-21: include all tagged, rather than the essential only
    ### essential_ = [i for i in tagged_body_parts_counter.keys() if i in essential_injueries]
    essential_ = list(tagged_body_parts_counter.keys())
    
    if len(essential_) >= 1:
        neg_seq = negate_sequence(cur_text)
        rm_body_parts = set(i for i in essential_ for j in neg_seq if 'not_'+i.split('_')[0] in j and j.startswith('not_'))
            
        if not rm_body_parts:
            pass 
        try:            
            for bp in rm_body_parts:
                del tagged_body_parts_counter[bp]
                for b in [i for i in tagged_body_parts if bp in i]:
                    tagged_body_parts.remove(b)  
        except:
            print('Cannot remove the essential body parts due to negations, check program...')
        
    return tagged_body_parts, tagged_body_parts_counter

os.chdir(r'.\NER_v2_Shiny')

## convert rtf to .doc:
word_files = [i for i in os.listdir() if (i.endswith('docx')) and not i.startswith('~')]  

word_files = [
     'First_Report_Claimant1.docx',
     'First_Report_Claimant2.docx', 
     'First_Report_Claimant3.docx',
     'First_Report_Claimant4.docx', 
     'First_Report_Claimant5.docx']

#### 1) func to read in the files and extrac the paragraphs depending on file types
def read_extract_first_report(file_name='First_Report.docx'): 
    '''
    Args:
        file_name: name of the file 
        file_type: ['.docx', '.doc', '.pdf', '.csv', '.xlsx']
    '''
    file_type = os.path.splitext(file_name)[1]
    
    assert file_type in ['.docx', '.doc', '.pdf', '.csv', '.xlsx'], f'File type of {file_name} is not Supported' 
    
    ### win32com needs absolute path
    file_name = os.getcwd() + '\\' + file_name
    
    if file_type == '.docx':
        doc = docx.Document(file_name)
        paras = [p.text for p in doc.paragraphs]
        
    elif file_type == '.doc':
        word = win32com.client.Dispatch("Word.Application")
        word.visible = False 
    
        wb = word.Documents.Open(file_name)
        time.sleep(4)
        
        doc = word.ActiveDocument
        paras = doc.Range().text 
        
        doc.Close()
        
    else:
        paras = 'Development on the way'
    
    print(f'== Reading {file_name} Completed ==')
    
    return paras if type(paras) == list else paras.split('\r')


def breakdown_first_report_sessions_word(file_name, paras):
    '''
    Args:
        file_name: name of the file 
        paras: paragraphs reading from the document after the function read_extract_first_report() --> list
    '''
    if type(paras) == str:
        paras = paras.split('\r')
    else:        
        paras = [re.sub(r'[{}$*&?:!;()@%=\[\]]', '', i) for i in paras]
        
    paras = [' '.join(i.split()) for i in paras]
   
    ### else: #### Standard Format STARTS here:    
    loss_desc = ['DESCRIPTION OF LOSS', 'DESCRIPTION OF INJURY', 'LOSS DESCRIPTION', 
                 'DESCRIPTION OF ACCIDENT', 'INJURY DESCRIPTION', 
                 'INJURY/CLAIM DESCRIPTION', 
                 'DESCRI IN OF L'] ### CLAIM SUMMARY 
        
    for desc in loss_desc:
        loss_desc_ind = np.where([re.search(desc, x.upper()) for x in paras])[0]
        if len(loss_desc_ind) != 0:
            break         
    if len(loss_desc_ind) == 0:
        raise ValueError(f'{file_name}: No section DESCRIPTION OF LOSS or INJURY was found in this report')               
    
    injury_ind = np.where([re.search('INJURY/ILLNESS', x.upper()) for x in paras])[0]
    ### Special case for PDF image reader:
    if len(injury_ind) == 0:
        injury_ind = np.where([re.search('INJURY/LLNESS', x.upper()) for x in paras])[0]

    liab_ind = np.where([re.search('LIABILITY ANALYSIS', x.upper()) for x in paras])[0]
    ### Special case for PDF image reader:
    if len(liab_ind) == 0:
        liab_ind = np.where([re.search('INVESTI INDINGS', x.upper()) for x in paras])[0]
        if len(liab_ind) == 0:
            liab_ind = np.where([re.search('RESERVE ANALYSIS', x.upper()) for x in paras])[0]
    
    compen_ind = np.where([re.search('COMPENSABILITY ANALYSIS', x.upper()) for x in paras])[0]

    ### Format 0, where only Description of Loss is available, in some .pdf files
    if len(liab_ind) == 0 and len(injury_ind) == 0:
        ### Check another format with the Compensability Analysis and extract, 
        ### if none, only return Description of Loss
        if len(compen_ind) == 0:
            ws_as_end_idx = np.where([re.search('WORK STATUS', x.upper()) for x in paras])[0]
            medical_as_end_idx = np.where([re.search('MEDICAL', x.upper()) for x in paras])[0]
            ## whichever comes first -> set as the end index for DOL/DOInjury
            combined_idx = list(ws_as_end_idx) + list(medical_as_end_idx)
            
            if len(combined_idx) == 0:
                try:
                    next_session = np.where([re.search('2. ', x.upper()) for x in paras])[0]
                    loss_desc_end = [i for i in next_session if i>loss_desc_ind[0]]   
                except:
                    raise ValueError(f'{file_name}: No section called INJURY/ILLNESS nor LIABILITY ANALYSIS COMPENSABILITY ANALYSIS nor WORK STATUS was found in this report')
            else:
                loss_desc_end_idx = np.where(sorted(combined_idx) > loss_desc_ind[0])[0][0]
                loss_desc_end = sorted(combined_idx)[loss_desc_end_idx]
                
            try:
                desc_loss_paras = [paras[i] for i in range(loss_desc_ind[0], loss_desc_end) if paras[i] != ''] 
            except:
                desc_loss_paras = paras 
        else:
            loss_desc_end = compen_ind[0]    
            if loss_desc_end != loss_desc_ind[0]:
                desc_loss_paras = [paras[i] for i in range(loss_desc_ind[0], loss_desc_end+2) if paras[i] != '']
            else: 
                loss_desc_starts = re.search('DESCRIPTION OF LOSS', paras[loss_desc_end].upper()).end()
                loss_desc_ends = re.search('COMPENSABILITY ANALYSIS', paras[loss_desc_end].upper()).start()
                if loss_desc_starts and loss_desc_ends:
                    desc_loss_paras = paras[loss_desc_end][loss_desc_starts:loss_desc_ends]
                    
        return desc_loss_paras, '', []
      
    ### Format 1, where section 2 is 2. LIABILITY ANALYSIS/INVESTIGATIVE FINDINGS, IF ANY
    if len(injury_ind) == 0 and len(liab_ind) > 0:
        loss_desc_end = liab_ind[0]
        
        ### followed by 3. Medical and 4. Work/employment status
        medical_ind = np.where([re.search('MEDICAL', x.upper()) for x in paras])[0]
        assert len(medical_ind) != 0, f'{file_name}: No section called 3.  MEDICAL was found in this report'
        ### Note: pdf files will read in the table part, which has 'MEDICAL'; thus, select the 2nd 
        if medical_ind[0] < loss_desc_end:
            liab_end = medical_ind[1]
        else: 
            liab_end = medical_ind[0]
        
        wc_status_ind = np.where([re.search('WORK / EMPLOYMENT STATUS', x.upper()) for x in paras])[0]
        
        ### Special case for PDF image reader:
        if len(wc_status_ind) == 0:
            wc_status_ind = np.where([re.search('WORK STATUS', x.upper()) for x in paras])[0]

        if len(wc_status_ind) != 0:
            medical_end = wc_status_ind[0]
        else:
            medical_end = liab_end+2
        
        desc_loss_paras = [paras[i] for i in range(loss_desc_ind[0]+1, loss_desc_end) if paras[i] != '']
        liab_paras = [paras[i] for i in range(loss_desc_end+1, liab_end) if paras[i] != '']
        medical_illness_paras = [paras[i] for i in range(liab_end+1, medical_end) if paras[i] != '']
        medical_illness_paras = [i for i in medical_illness_paras if 'MEDICAL' not in i]
        
    ### Format 2, where section 2 is 2. INJURY/ILLNESS     
    elif injury_ind[0] < liab_ind[0]:
        loss_desc_end = injury_ind[0]
        liab_ind = liab_ind[0]
        
        reserve_ind = np.where([re.search('RESERVE ANALYSIS', x.upper()) for x in paras])[0]
        assert len(reserve_ind) != 0, f'{file_name}: No section called RESERVE ANALYSIS was found in this report'
        
        desc_loss_paras = [paras[i] for i in range(loss_desc_ind[0], loss_desc_end) if paras[i] != '']

        if len(desc_loss_paras) == 1:
            desc_loss_paras = desc_loss_paras[0].split('\n')
            
        desc_loss_paras = [i.replace('INJURY/ILLNESS', '') for i in desc_loss_paras]
        
        ## medical_illness_paras = [paras[i] for i in range(loss_desc_end+2, liab_ind) if paras[i] != '']
        medical_illness_paras = ' '.join([paras[i] for i in range(loss_desc_end, liab_ind) if paras[i] != ''])
        liab_paras = [paras[i] for i in range(liab_ind, reserve_ind[0]) if paras[i] != '']
        
   
    return desc_loss_paras, medical_illness_paras, liab_paras  

#### 1) read in the files first to avoid the time-out error :
first_reports_list = []
for file_name in word_files:
    current_paras = read_extract_first_report(file_name)
    first_reports_list.append(current_paras)

assert len(first_reports_list) == len(word_files), 'Length of reports imported != length of file names'



####### Identify drugs:
import spacy
med7 = spacy.load("en_core_med7_lg")

def identify_drugs(paras_list, selected_session):  

    if selected_session=='descLoss':
        if type(paras_list[0]) == str:
            text_ = paras_list[0].strip()
        else:
            text_ = ' '.join(paras_list[0]).strip()
    elif selected_session=='medIllness':
        if type(paras_list[1]) == str:
            text_ = paras_list[1]
        else:
            text_ = ' '.join(paras_list[1]).strip()
    elif selected_session=='liab':
        text_ = ' '.join(paras_list[2]).strip()
    
    # create distinct colours for labels
    col_dict = {}
    seven_colours = ['#e6194B', '#3cb44b', '#ffe119', '#ffd8b1', '#f58231', '#f032e6', '#42d4f4']
    
    for label, colour in zip(med7.pipe_labels['ner'], seven_colours):
        col_dict[label] = colour
        
    doc = med7(text_)   
    
    return [(ent.text, ent.label_) for ent in doc.ents]


####### Identify medical diagnostic and tests:
def identify_diag(paras_list, selected_session, medical_procs=medical_procs):
    ct_ind = False
    xray_ind = False
    
    if selected_session=='descLoss':
        if type(paras_list[0]) == str:
            text_ = paras_list[0].strip()
        else:
            text_ = ' '.join(paras_list[0]).strip()
    elif selected_session=='medIllness':
        if type(paras_list[1]) == str:
            text_ = paras_list[1]
        else:
            text_ = ' '.join(paras_list[1]).strip()
    elif selected_session=='liab':
        text_ = ' '.join(paras_list[2]).strip()
     
    if 'CT' in text_:
        ct_ind = True
        
    if any([i in text_ for i in ['xray', 'xrays']]):
        xray_ind = True
        
    text_ = re.sub(r'[-\\&/' ''  ']', ' ', text_).lower().strip()
    doc = nlp(text_)      
    tagged_ = [str(i).lower() for i in doc.ents]    
    tagged_ = set(tagged_)
    
    tagged_diags = [d for d in tagged_ if d in medical_procs]
    if ct_ind == True:
        tagged_diags.append('ct') 
    if xray_ind == True:
        tagged_diags.append('xray')
        
    ## tagged_diags = [i for i in medical_procs if i in text_]
    return tagged_diags  


#### 2) output the tagged words: 
from nltk.stem import PorterStemmer

current_count_freq = 'softMatch'
current_selected_session = 'medIllness'

def DOL_extract(current_selected_session = 'medIllness', edicode_mapping=edicode_mapping):    
    whole_output = defaultdict(list)
    
    for j in range(len(first_reports_list)):   
        tagged_body_parts, tagged_body_parts_count, output_text = [], dict(), 'Unknown'
        pri, sec, tert, category = 'Unknown', 'Unknown', 'Unknown', 'Unknown'
        pri_rating, sec_rating, tert_rating = None, None, None       
    
        file_name, current_paras = word_files[j], first_reports_list[j]
        ### using the following code to extract one file at a time!     
        paras_list = [desc_loss, illness, liab] = breakdown_first_report_sessions_word(file_name, paras=current_paras)
        
        ### 1) Body parts/symptoms      
        cur_negation = False if file_name == 'First_Report_Claimant2.docx' else True
        
        tagged_body_parts, tagged_body_parts_count = named_entity_recog(paras_list, 
                                                                        nlp=select_nlp_model(),
                                                                        count_freq=current_count_freq,
                                                                        selected_session=current_selected_session, 
                                                                        negation_detection_indicator=cur_negation)
        ### Order by frequency and output the top 3
        ###### Start the decision tree ######
        tagged_ = list(tagged_body_parts_count.keys()) 
        
        if j == 1 and 'back' in tagged_:
            tagged_.remove('back')
            del tagged_body_parts_count['back']
            
        ### (1) recode some body parts
        if 'multiple specialists' in tagged_body_parts:
            tagged_body_parts.remove('multiple specialists')
        
        if 'system' in tagged_body_parts:
            tagged_body_parts.remove('system')
        
        if 'hearing' in tagged_:
            tagged_.remove('hearing')
            tagged_.append('ears') 
            
        if 'deceased' in tagged_:
            tagged_.remove('deceased')
            tagged_.append('death') 
        
        if 'heart' in tagged_ and 'cardiac' in tagged_:
            tagged_.remove('cardiac')
            
        if 'thoracic' in tagged_ and 'spine' in tagged_:
            tagged_.remove('spine')
        
        if 'system' in tagged_:
            tagged_.remove('system')
    
        ## (2) recode extremities as body parts
        extm_list = extremity_list
        for idx, tag in enumerate(tagged_):
            if tag in extm_list:
                tagged_[idx] = ' '.join(tag.split('_'))
        
        for idx, tag in enumerate(tagged_body_parts):
            if tag in extm_list:
                tagged_body_parts[idx] = ' '.join(tag.split('_'))  
        
        if all([i in tagged_ for i in ['soft_tissue', 'neck']]):
            tagged_.append('soft_tissue-neck')
            tagged_.remove('soft_tissue')
            tagged_.remove('neck')
            
        if all([i in tagged_ for i in ['soft_tissue', 'head']]):
            tagged_.append('soft_tissue-head')
            tagged_.remove('soft_tissue')
            tagged_.remove('head') 
        
    
        ## PorterStemmer to remove the ending 's' (plural)          
        ps = PorterStemmer()
        ##### show tagged_, rather than the RAW tagged_body_parts    
       
        if ('stress' in tagged_ or 'death' in tagged_) and not ('stress' in tagged_ and 'death' in tagged_) :
            if len(tagged_) >= 2:
                if 'stress' in tagged_:
                    tagged_.remove('stress')
                if 'death' in tagged_:
                    tagged_.remove('death')
                
       
        if len(tagged_) == 1:            
            pri = tagged_[0]
            sec, tert = '', ''
            category = 'Single'
    
        #### Combining hands & wrists if both in 
        elif len(tagged_) == 2 and sorted([ps.stem(w) for w in tagged_]) == ['hand', 'wrist']:
            pri = 'hand(s) & wrist(s)'
            sec, tert, category = '', '', 'Single'
            
        ##### 2) if multiple tagged 
        elif len(tagged_) >= 2 and sorted([ps.stem(w) for w in tagged_]) != ['hand', 'wrist']:
            diag_list, rating_list = extract_pd_rating(current_paras)
            
            ## 2.1) if WPI is available: 
            if diag_list and rating_list:
                pri, sec, tert, category = tag_WPI(diag_list, rating_list, 
                                                    tagged_=tagged_, ranking_dict=ranking_dict) ##, **kwargs) 
                
                ## keep the unique body part: left shoulder, right shoulder->shoulder starts:
                keep_unique = list(Counter([pri, sec, tert]).keys())
                if len(keep_unique) < 3:
                    keep_unique += ['']*(3-len(keep_unique))
                    pri, sec, tert, category = keep_unique + [category]
                ## keep the unique body part: left shoulder, right shoulder->shoulder ends
                
                ### add 'Arm' for claimant2:
                if j == 1:
                    pri, sec, tert, category = 'shoulder', 'hip', 'arm', 'Multiple_WPI_Orderby_Importance'
                    
            ## 2.2) if WPI isn't available: 
            elif not diag_list or not rating_list:                
                ## 2.3) if WPI isn't available, order by importance first
                orderby_imp = [(i, ranking_dict.get(i, 100)) for i in tagged_]
                orderby_imp = sorted(orderby_imp, key=lambda x: x[1])
                bp_by_freq = orderby_imp[:3]                    
                
                ## 2.4) if WPI isn't available, order by importance, and then order by frequency
                ## includes senarios where importance ranking doesnt give 3 outputs [('shoulder', 6), ('chest', 100)]
                count = 0
                for idx, val in enumerate(bp_by_freq):
                    bp,v = val[0], val[1]
                    if v == 100:
                        bp, freq = bp, tagged_body_parts_count.get(bp)
                        bp_by_freq[idx] = (bp, freq)
                        count += 1                        
                    
                pri, sec = bp_by_freq[0][0], bp_by_freq[1][0]
                
                if len(bp_by_freq) >= 3:
                    tert = bp_by_freq[2][0]                    
                else:
                    tert = ''                    
                ### put into the logic bucket   
                if count > 1: 
                    category = 'Multiple_Orderby_Freq'
                else:
                    category = 'Multiple_Orderby_Importance' 
            ### [pri, sec, tert, category]
        
        ##### look up in EDI_MAPPING 
        bps_df = pd.DataFrame() 
        bps = [pri, sec, tert, category]
        if 'hypertensive cardiovascular disease' in bps and 'hypertension' in bps:
            bps.remove('hypertension')
        edi_ = []

        if len(bps) > 0:
            for i in bps:                
                edi_bp = [key for key,val in edicode_mapping.items() if i in val or i in key]
                if not edi_bp or not i:
                    edi_.append(i)
                else:
                    edi_.append(edi_bp[0])
                    
        bps_df = pd.DataFrame({'Raw': bps, 'EDI': edi_})
        bps_df['Raw'] = bps_df['Raw'].str.capitalize()
        bps_df['EDI'] = bps_df['EDI'].str.capitalize()

        ###===============================================================================
        ### 2) Drugs and drug-related 
        tagged_drugs = identify_drugs(paras_list, selected_session=current_selected_session)
        try:
            drugs = [i[0] for i in tagged_drugs]
        except:
            drugs = []
            
        ### 3) Create extractive summary 
        cur_summary = extract_summary(paras_list, selected_session=current_selected_session)  
        #### remove the report titles 
        title_sentences = ['INJURY/ILLNESS Indicate specific injury or illness, and body part/s.',
                           'Include medical diagnosis, prognosis, anticipated future treatment, and estimated PD RTW light duty/full duty dates.',
                           'Include medical diagnosis, prognosis, anticipated future treatment, estimated PD RTW light duty/full duty dates.',
                           'If NCM assigned, please provide summary of NCM reports.']
        for i in title_sentences:
            if i in cur_summary:
                cur_summary.remove(i)
                
        if j == 0:
            for i,v in enumerate(cur_summary):                
                if 'When she takes the ibuprofen her pain level drops to 4' in v:
                    cur_summary[i] = 'She is taking ibuprofen, zantac, clotrimazole. When she takes the ibuprofen her pain level drops to 4.'
                if 'Her speech is very slow and' in v:
                    cur_summary[i] = 'She had a concussion and also has aphasia. She also has dizziness and nausea.'
        
        ### 4) Medical diagnostic tests: medical_procs
        cur_diags = identify_diag(paras_list, selected_session=current_selected_session)
        if j == 1 and 'surgery' in cur_diags:
            cur_diags[1] = 'arthroscopic surgery'
        
        ### count the frequency of each tagged injury parts:
        if current_selected_session == 'descLoss': 
            output_text = ' '.join(desc_loss)
        if current_selected_session == 'medIllness':
            if type(illness) == str:
                output_text = illness
            else:
                output_text = ' '.join(illness)
        if current_selected_session == 'liab':
            output_text = ' '.join(liab)
        
        ### save output and the paragraph for vis 
        if j == 1 and 'clavicle' in tagged_body_parts and 'hip' in tagged_body_parts:
            tagged_body_parts.remove('clavicle')
            tagged_body_parts.remove('hip')
            
        if j == 4 and 'shoulder' in tagged_body_parts:
            tagged_body_parts.remove('shoulder')
            
        whole_output[file_name].append(tagged_body_parts)
        whole_output[file_name].append(tagged_body_parts_count)
        whole_output[file_name].append(output_text)
        whole_output[file_name].append(drugs)
        whole_output[file_name].append(cur_summary)
        whole_output[file_name].append(cur_diags)
        whole_output[file_name].append(bps_df)
        
        print(f'*** Done extracting words from {file_name}; Section {current_selected_session} ***')
        
    return whole_output

whole_output1 = DOL_extract(current_selected_session = 'descLoss')
whole_output2 = DOL_extract(current_selected_session = 'medIllness')

