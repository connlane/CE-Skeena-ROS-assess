'''
DRAFT

Changes this run: changed range to traverse the field, percent dictionary pairs (changed form len(list)-1 to len(list))

comment test

TODOs:  TODO seperate steps into different try/except blocks TODO use variable during initial loop to store largest % area of ROS cat (save the list and dictionary later on) TODO improve comments and logging
'''

import os, time, arcpy, csv, logging, datetime # long list of dependencies


# TODO set workspace needs to go up one directory from __file__ then into ArcProj\ROS.gdb
    # print(os.path.abspath(os.path.join(__file__, os.pardir)))

arcpy.env.overwriteOutput = True

#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# Run the assessment using the csv containing the layer names in ROS_assessment.gdb
layers = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ROS_layers.csv') # assumes the .csv is in the same folder as the script
paths_dict = {} # the dictionary holds the layer's nickname and layer path from the CSV
with open(layers, 'r') as table: # read the csv 
    reader = csv.reader(table)
    next(reader, None) # this skips the first row - the column names
    for row in reader:
        k, v = row
        paths_dict[k]=v
workspace = paths_dict['workspace']
arcpy.env.workspace = workspace
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
log_tag = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M')
log_file = os.path.join(os.path.dirname(__file__), 'LogFile_{}.log'.format(log_tag))
logging.basicConfig(level=logging.DEBUG,
    format='%(asctime)s:%(levelname)-4s:\t%(message)s',
    datefmt='%Y=%m-%d %H:%M:%S',
    filename=log_file,
    filemode='a') #'a' appends to an existing file while 'w' overwrites anything already in the file
logging.info('START LOGGING')
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
def ROS_summary(in_aoi, in_ROS, in_AU):
    tag = time.strftime("%y%m%d")
    startTime = time.time()
    START_TIME = time.ctime(startTime)
    print('\nStarting: {}'.format(START_TIME))
    logging.info('\nStarting: {}'.format(START_TIME))
    fwa_sel = arcpy.management.SelectLayerByLocation(in_AU, 'INTERSECT', in_aoi)
    area_name = in_aoi.rsplit('\\', 1)[-1] # cannot use r'\' in rsplit, use '\\'
    fwa_export = r'ROS_Summary_{}_{}'.format(area_name, tag) # Copy selected AU features - this is the output layer
    arcpy.conversion.FeatureClassToFeatureClass(fwa_sel, workspace, fwa_export)
    keep_list = ['WATERSHED_GROUP_CODE', 'WATERSHED_FEATURE_ID', 'OBJECTID', 'Shape', 'Shape_Length', 'Shape_Area', 'AREA_HA', 'FEATURE_AREA_SQM', 'FEATURE_LENGTH_M']
    field_list = arcpy.ListFields(fwa_export) # delete extraneous FWA fields from AU table
    for field in field_list:
        if field.name not in keep_list:
            arcpy.management.DeleteField(fwa_export, '{}'.format(field.name))    
    #--------------------------------------------------------------
    # Do the ROS assessment
    try:
        ros_clip = 'ROS_{}_clip_{}'.format(area_name, tag)
        arcpy.analysis.PairwiseClip(in_ROS, fwa_export, ros_clip) # don't clip to just the AOI as the AU selection will be a litle larger
        category_list = [] # list of ROS categories
        with arcpy.da.SearchCursor(ros_clip, ['REC_OPP_SPECTRUM_CODE']) as cursor:
            for row in cursor:
                if row[0] not in category_list:
                    category_list.append(row[0])
        print(category_list)
        outputs_list = []
        for cat in category_list: #Approx 40 seconds per iteration
            field_ha = '{}_Area_HA'.format(cat)
            field_pct = '{}_Area_PCNT'.format(cat)
            outputs_list.append(field_pct)
            arcpy.management.AddField(fwa_export, field_ha, "FLOAT", field_is_nullable='TRUE')
            arcpy.management.AddField(fwa_export, field_pct, "FLOAT", field_is_nullable='TRUE')
            ros_sel = arcpy.management.SelectLayerByAttribute(ros_clip, 'NEW_SELECTION', """REC_OPP_SPECTRUM_CODE = '{}'""".format(cat))
            if int(str(arcpy.management.GetCount(ros_sel))) > 0:
                out_sum = r'FWA_AU_ROS_{}'.format(cat) #non static output name to be used later to update fwa_export
                arcpy.analysis.SummarizeWithin(fwa_export, ros_sel, out_sum, 'KEEP_ALL', '', 'ADD_SHAPE_SUM', 'HECTARES')
                scursor = [row[0] for row in arcpy.da.SearchCursor(out_sum, ("sum_Area_HECTARES"))]
                ucursor = arcpy.da.UpdateCursor(fwa_export, ['AREA_HA', field_ha, field_pct])
                i=0
                for row in ucursor:      
                    row[1] = round(scursor[i], 2)
                    row[2] = round(float(scursor[i])/float(row[0])*100, 2)
                    i+=1
                    ucursor.updateRow(row)
                arcpy.management.Delete(out_sum)
                del scursor, ucursor
            else:
                print('No area overlap for {}'.format(out_sum))
                logging.info('No area overlap for {}'.format(out_sum))
                ucursor = arcpy.da.UpdateCursor(fwa_export, [field_ha, field_pct])
                for row in ucursor:      
                    row[0] = 0.0
                    row[1] = 0.0
                    ucursor.updateRow(row)
            logging.info('{} iteration completed'.format(cat))
            print('------------------------------------')
    except:
        print('\nUnable to complete ROS assessment steps')
        print(arcpy.GetMessages())
        logging.error(arcpy.GetMessages())
    totalTime = time.strftime("%H:%M:%S",time.gmtime(time.time() - startTime))
    print('\nThe ROS assessment took {} to run'.format(totalTime))
    # -------------------------------------------------------------------------------------------------
    # clunky way of extracting the ROS category from the percent area field that was calculated above. Possible to use a variable to hold the highest area within the category loop?
    # Use search cursor to get the pcnt areas for each fow in fwa_export. Sort list of percent areas to put highest area first. 
    # Use a dictionary that was created before sorting list to match the ROS cat with the percent area even after soring. No search the dict by largest area to extract the ROS category
    # try:
    new_field = 'Predominant_ROS_Cat'
    arcpy.management.AddField(fwa_export, new_field, 'TEXT', field_is_nullable=True)
    outputs_list.insert(0, new_field) # Can specify the index in list to insert the object using list.INSERT(). Unlike list.APPEND() which just tacks on the new object at the end
    print(outputs_list)
    successcount = 0
    iteration = 0
    with arcpy.da.UpdateCursor(fwa_export, outputs_list) as cursor:
        for row in cursor:
            iteration += 1
            fields_dict = {}
            sorted_list = row[1:] # need to compare the ROS cat area % to find the category with the largest %
            for i in range(1, len(outputs_list)): # 
                fields_dict[outputs_list[i]] = row[i] # need to add field, percent pairs into the dictionary. If not in dictionary, cannot get the ROS category out of the area percent
            sorted_list.sort(reverse=True) # Sort list in descending order - ie largest % first
            search_val = sorted_list[0] # Need to do this because dictionaries are not ordered - for each par in the dictionary, we will compare values to this search_val (the greatest % of ROS cat) 
            for field, pct in fields_dict.items():
                if pct == search_val:
                    row[0] = field[:-10] # Assign the new_field to the ROS category that's the greatest % of the AU being evaluated. The entire field string is like 'RN_Area_PCNT', so slice off the last 10 chars to only have the ROS category code remaining
                    logging.info("{}: success {}".format(iteration, field[:-10]))
                    successcount+=1
                    break
                else:
                    logging.info('{}: {} was compared to {}'.format(iteration, pct, search_val))
            cursor.updateRow(row)
            del fields_dict
    print(successcount)
    print(iteration)
    logging.info('{} of {} AUs assigned ROS category'.format(successcount, iteration))
    arcpy.management.Delete(ros_clip)
    logging.info('FUNCTION COMPLETE')
    # except:
    #     print('\nUnable to complete greatest area ROS category assignment for assessment watershed')
    #     print(arcpy.GetMessages())
    #     logging.error(arcpy.GetMessages())
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# Call the function on the layers        
ROS_summary(paths_dict['area'], paths_dict['ROS'], paths_dict['fwa'])

# TODO Jesse thinks it might work to use a list par inside a Tuple instead of the dictionary mess