'''
DRAFT

Changes this branch: Add rules to group the AUs based on their predominant ROS categories, include a field in the mine_check section to store the unadjusted predominant ROS category

TODOs:  TODO seperate steps into different try/except blocks TODO improve comments and logging


Copyright 2019 Province of British Columbia

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at 

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

'''

import os, time, arcpy, csv, logging, datetime # long list of dependencies


#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# Run the assessment using the csv containing the layer names in ROS_assessment.gdb
layers = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ROS_layers.csv') # assumes the .csv is in the same folder as the script
paths_dict = {} # the dictionary holds the layer's nickname and layer path from the CSV
with open(layers, 'r') as table: # read the csv 
    reader = csv.reader(table)
    next(reader, None) # this skips the first row - the column names
    for row in reader:
        k, v = row # CSV is laid out left to right: layer nickname (k) then layer path (v)
        paths_dict[k]=v
workspace = paths_dict['workspace']
arcpy.env.workspace = workspace
arcpy.env.overwriteOutput = True
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
log_tag = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M')
log_file = os.path.join(os.path.dirname(__file__), 'ROS_LogFile_{}.log'.format(log_tag))
logging.basicConfig(level=logging.DEBUG,
    format='%(asctime)s:%(levelname)-4s:\t%(message)s',
    datefmt='%Y=%m-%d %H:%M:%S',
    filename=log_file,
    filemode='a') #'a' appends to an existing file while 'w' overwrites anything already in the file
logging.info('START LOGGING')
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# include function to check for presence of mines and adjust the field as required # TODO add an AU buffer of mines
# function called near end of ROS_summary
def mine_check(in_layer, in_field, in_val, *in_check): # eg Pass to function: ROS assessment output layer, name of the field to update, value to set the field to, the mines layer to check for presence
    new_layer = '{}_mine_adjustment'.format(in_layer.rsplit('\\', 1)[-1]) 
    print(new_layer)
    arcpy.conversion.FeatureClassToFeatureClass(in_layer, workspace, new_layer) # make a new layer to preserve the results of ROS assessment
    mine_aus = [] # add empty list of OIDs 
    # TODO add the empty csv structure? want to save a summary table of all the AUs that contain mines
    for mine in in_check:
        # if 'TRIM' in mine:
            # check_sel = arcpy.management.SelectLayerByAttribute(mine, 'NEW_SELECTION', "FEATURE_TYPE IN ('mine', 'mineOpenPit', 'quarry')") # need to query the TRIM attributes
            # check_sel = arcpy.management.SelectLayerByLocation(new_layer, 'CONTAINS', check_sel) # TODO check the open/closed status
        # else:
        check_sel = arcpy.management.SelectLayerByLocation(new_layer, 'INTERSECT', mine, selection_type='ADD_TO_SELECTION') # using expanded mine selection
        print('Features to update in {}: {}'.format(mine, arcpy.management.GetCount(check_sel))) # print the layer path and how many features were selected, 
    new_field = 'prev_ROS_code' # add a field to store what the ROS code was before being changed to 'R'
    arcpy.management.AddField(new_layer, new_field, 'TEXT', field_is_nullable = True) # field will be null for any AUs that do not have a mine. but what about those that are in the buffer?
    counter=0
    with arcpy.da.UpdateCursor(check_sel, [in_field, new_field]) as cursor: # change the AUs that have a mine in them to ROS code 'R'
        for row in cursor:
            if row[0] != in_val: # check that the ROS code actually needs to be changed, in_val = 'R', couldn't this be hard coded? yes, but should it?
                row[1] = row[0] # set the new field attribute to the old ROS category before updating field due to presence of a current or historical mine
                row[0] = in_val # For each selected feature, change the field value to the input argument
            cursor.updateRow(row)
            counter+=1
    print(counter)
    ROS_dict = {
        1: 'R',
        2: 'RM',
        3: 'RN',
        4: 'SPM',
        5: 'SPNM',
        6: 'P'
    } # dictionary of the ROS codes assigned to an int in increasing order of recreation opportunity (ie higher the in, the 'better' the ROS code) 
    print(arcpy.management.GetCount(check_sel))
    boundary_sel = arcpy.management.SelectLayerByLocation(new_layer, "BOUNDARY_TOUCHES", check_sel)
    print(arcpy.management.GetCount(boundary_sel))
    boundary_sel = arcpy.management.SelectLayerByLocation(boundary_sel, 'ARE_IDENTICAL_TO', check_sel, selection_type='REMOVE_FROM_SELECTION') # remove the already adjusted feature from this seleciton
    print(arcpy.management.GetCount(boundary_sel)) # second num of boundary_sel should be smaller since we have removed from the selection all the AUs that contain mines and have already been adjusted
    with arcpy.da.UpdateCursor(boundary_sel, [in_field, new_field]) as cursor:
        for row in cursor:
            if not row[1]: # double check that we have not already adjusted this AU - if row[1] is not null, do the stuff
                for num, code in ROS_dict.items(): # this nested for loop is not good practice. I'm not quite sure how else to get the key out of ROS_dict if it's not the item in the dict being evaluated
                    if row[0] == code: # only 1 of the 6 items in the dict are necessary
                        row[1] = row[0] # update the new_field to store what the previous ROS code was
                        if num >= 2:
                            row[0] =  ROS_dict[num-1] # set the predominant ROS code to the next worse code
                        else:
                            row[0] = ROS_dict[1]
            cursor.updateRow(row)
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
                    category_list.append(row[0]) # Get the categories that exist within the ROI (no areas categorized as urban in Skeena region)
        print(category_list)
        outputs_list = []
        for cat in category_list: #Approx 40 seconds per iteration
            print(cat)
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
    outputs_list.insert(0, new_field) # Can specify the index in list to insert the object using list.INSERT(index, element). Unlike list.APPEND() which just tacks on the new list element at the end
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
    mine_check(fwa_export, new_field, 'R', paths_dict['trim_mines'], paths_dict['min_mines'])
    arcpy.management.Delete(ros_clip)
    logging.info('FUNCTION COMPLETE')
    # except:
    #     print('\nUnable to complete greatest area ROS category assignment for assessment watershed')
    #     print(arcpy.GetMessages())
    #     logging.error(arcpy.GetMessages())
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# Call the function on the layers from paths_dict        
ROS_summary(paths_dict['area'], paths_dict['ROS'], paths_dict['fwa'])

# TODO Jesse thinks it might work to use a list pair inside a Tuple instead of the dictionary mess? I fixed the problem with my dictionary because I was not terating through the full list length, just len()-1