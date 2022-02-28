library(shiny)
library(shinybusy)
library( shinyWidgets )
library(stringr)
library(DT)
library(magrittr)
library(knitr)
library(reticulate)
library(shinythemes)
library(reshape)
library(shinyWidgets)
library(scales)
library(readxl)
library(lubridate)
library(tibble)
library(writexl)
library(openxlsx)

options(scipen = 999)

py_run_string("import os as os")
py_run_string("os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = 'C:/Users/YLi/miniconda3/Library/plugins/platforms'")

source_python('./NER_v2_forShiny.py')

wordHighlight <- function(SuspWord, colH = 'yellow') {
    paste0('<span style="background-color:',colH,'">',SuspWord,'</span>')
}

wordHighlight_drugs <- function(SuspWord, colH = 'lightgreen') {
  paste0('<span style="background-color:',colH,'">',SuspWord,'</span>')
}

wordHighlight_diags <- function(SuspWord, colH = 'lightpink') {
  paste0('<span style="background-color:',colH,'">',SuspWord,'</span>')
}

  
#####==============================================================########
##### UI starts here:
#####==============================================================########
## ui <- fluidPage(
ui <- navbarPage(
        theme = shinytheme("united"),
        'NLP Toolkit',
        
        tabPanel('EHRs Processor', 
                 sidebarLayout(
                   sidebarPanel(
                     width = 3,
                     
                     img(src = 'NLP2.png',   ###'PRISM.png', 
                         align = "center",
                         width = '100%',
                         style="height: 95px"),
                     
                     br(),
                     br(),
        
                     radioButtons("section", "Select a section:", c("Description of Loss" = 'DOL', "Injury/Illness" = "INJ"), 
                                  selected = 'INJ'),
                     
                     selectInput("fn", "Select a File to review", choices = names(whole_output1), selected = 'First_Report_Claimant2.docx'),
                     
                     prettyCheckbox(
                       inputId = "colors_on",
                       label = "Let the magic happen!",
                       outline = TRUE,
                       plain = TRUE,
                       animation = "tada",
                       bigger = TRUE, 
                       icon = icon("thumbs-up")
                     ),
                     
                     checkboxInput("check_top3", "Top 3 Body Parts/injuries", FALSE),
                     
                     DT::dataTableOutput('tagged')

                   ),
                   mainPanel(
                     DT::dataTableOutput('edi'),
                     
                     DT::dataTableOutput("table"), 
                     br(), 
                     DT::dataTableOutput('table_summary')
                   )
              )
          ),    #### tabPanel Claims Reports Summarizer
        
        tabPanel('Utilities', 
                 mainPanel(
                   DT::dataTableOutput('deNotes')
                 )
                 
        )    #### De-identification notes
        
  )


#####==============================================================########
##### SERVER starts here:
#####==============================================================########
server <- function(input, output, session) {
  ####===================================####
  ####==== Claims Reports Summerizer ====####
  ### 0. create whole_output 
  whole_output = reactive({
    if(input$section == 'DOL'){
      out = whole_output1
    } else {
      out = whole_output2
    }
    return(out)
  })

  ### 1. tagged_words
  output$tagged = DT::renderDataTable({
    whole_output = whole_output()
    if(input$colors_on){
      output_file = whole_output[input$fn]
      data.frame("Body_Parts(Symptoms_Diagnosis)" = output_file[1][[1]])
    } else NULL
    
  }, options = list(pageLength = 100, info = FALSE, dom = 't'))
  
  ## 2. counts
  output$counts = renderText({
    whole_output = whole_output()
    output_file = whole_output[input$fn]
    
    toString(output_file[2][[1]])
  })
  
  output$deNotes = DT::renderDataTable({
    s1 = "Replace claimant's real names with 'This claimant'; Remove other names, e.g., claimant's sister's name"
    s2 = "Replace Drs' real names with Dr.ABC/DEF etc."
    s3 = "Replace Hospital names with 'The hospital'"
    s4 = "Replace real DOL or claim-related dates with '1900-01-01' or '1900-01-01 to 1900-01-03' etc."
    s5 = "Replace claimants's real ages with 50"
    s6 = "Replace all geographical locations with 'California'"
    ## s7 = "Replace real medication names with randomly picked OTC medications; Dosages are random numbers"
    s7 = paste0('Replace real medication names with randomly picked ', 
                paste0('<a  target=_blank href=', 'https://www.aetnabetterhealth.com/illinois/assets/pdf/pharmacy/OTC-IL.pdf', '>','OTC medications','</a>'), 
                '; Dosages assigned are random numbers')
    df = data.frame(Claims_Reports_Deidentification_Notes = rbind(s1, s2, s3, s4, 
                                                                  s5, s6, s7))
    rownames(df) = NULL 
    df
  }, escape = FALSE)

  ## 2. top 3 EDI mapping 
  output$edi = DT::renderDataTable({
    if(input$check_top3) {
      whole_output = whole_output()
      
      output_file = whole_output[input$fn]
      df = output_file[7][[1]]   #### data.frame(Body_Parts = output_file[7][[1]])
      
      if (dim(df)[1] == 3) {
        df[3, ] = NA
        rownames(df) = c('Primary', 'Secondary', 'Tertiary')
      } else {
        df = df[-nrow(df), ]
        rownames(df) = c('Primary', 'Secondary', 'Tertiary')
      }
      
      data.frame(Body_Parts = df)
    } else NULL
    
  }, options = list(pageLength = 100, info = FALSE, dom = 't'))
  

  ### 3. whole text highlighted
  getData = reactive({
    whole_output = whole_output()
    
    output_file = whole_output[input$fn]

    sentence <- output_file[[3]]
    summary <- output_file[[5]]
    
    YourData = data.frame(Original_Text = sentence, stringsAsFactors = FALSE)
    SummaryData = data.frame(Summary_Text = summary, stringsAsFactors = FALSE)
    
    tagged_words_list = output_file[[1]]
    tagged_words_list = gsub('_', ' ', tagged_words_list)
    
    ### move all 'back' related body parts upfront to avoid 'back' replacing <span style=\"background-color:yellow\"> that is already formatted 
    back_idx = which(grepl('back', tagged_words_list))
    if(length(back_idx) > 0){
      tagged_words_list = tagged_words_list[c(back_idx, seq(length(tagged_words_list))[-back_idx])]
    }
    
    tagged_drugs_list = output_file[[4]]
    tagged_diags_list = output_file[[6]]

    if('Left shoulder full thickness supraspinatus' %in% tagged_words_list){
      tagged_words_list[which(tagged_words_list == 'Left shoulder full thickness supraspinatus')] = 'Left shoulder full-thickness supraspinatus'
    }
    
    if('back spine' %in% tagged_words_list){
      tagged_words_list[which(tagged_words_list == 'back spine')] = 'back/spine'
    }
    if( all(c("lumbar", "spine", 'lumbar spine') %in% tagged_words_list)){
      tagged_words_list = tagged_words_list[!tagged_words_list %in% c("lumbar", "spine")]
    }
    if(all(c("disc", "degenerative disc disease") %in% tagged_words_list)){
      tagged_words_list = tagged_words_list[!tagged_words_list %in% c("disc")]
    }
    if(all(c("back", "lower back") %in% tagged_words_list)){
      tagged_words_list = tagged_words_list[!tagged_words_list %in% c("back")]
    }
    
    ### for original and summary: str_replace_all to replace ALL occurances, not just the 1st one
    #======= BODY PARTS:
    if (input$colors_on){
      for (patterns in tagged_words_list) {
        YourData[, 1] %<>% str_replace_all(regex(patterns, ignore_case = TRUE), wordHighlight)
        SummaryData[, 1] %<>% str_replace_all(regex(patterns, ignore_case = TRUE), wordHighlight)
      }
    }
      
    #======= DRUGS: ##### check if has IV
    if (input$colors_on){
      for (drug in tagged_drugs_list){
        # YourData[, 1] %<>% str_replace(regex(drug, ignore_case = TRUE), wordHighlight_drugs)
        # SummaryData[, 1] %<>% str_replace_all(regex(drug, ignore_case = TRUE), wordHighlight_drugs)
        drug = sprintf('\\b%s\\b', drug)
        YourData[, 1] %<>% str_replace_all(regex(drug, ignore_case = TRUE), wordHighlight_drugs)   ### !!! now str_replace_all
        SummaryData[, 1] %<>% str_replace_all(regex(drug, ignore_case = TRUE), wordHighlight_drugs)
      }
    }
    
    #======= DIAGS:
    if (input$colors_on) {
      for (diag in tagged_diags_list){
        if(diag %in% c('CT', 'ct')){  #### alternatively, check if starts with CT 
          diag_pattern = sprintf('\\b%s\\b', diag)
          YourData[, 1] %<>% str_replace_all(regex(diag_pattern, ignore_case = TRUE, perl = TRUE), wordHighlight_diags)   ### !!! str_replace_all
          SummaryData[, 1] %<>% str_replace_all(regex(diag_pattern, ignore_case = TRUE, perl = TRUE), wordHighlight_diags)
          
        } else{
          YourData[, 1] %<>% str_replace(regex(diag, ignore_case = TRUE, type = 'word'), wordHighlight_diags)
          SummaryData[, 1] %<>% str_replace_all(regex(diag, ignore_case = TRUE, type = 'word'), wordHighlight_diags)
        }
      }
    }
    
    return (list(OriginalData = YourData, 
                 SummaryData = SummaryData)
            )
  })
  
  ## render Original table with CSS
  output$table <- DT::renderDataTable({
    data = getData()$OriginalData
  }, escape = FALSE, options = list(info = FALSE, dom = 't'))
  
  
  ## render Summary table with CSS
  output$table_summary <- DT::renderDataTable({
    data = getData()$SummaryData
  }, escape = FALSE, options = list(orderFixed = 'asc', 
                                    pageLength=25)) ## , pageLength=20
  
}

shinyApp(ui = ui, server = server)























