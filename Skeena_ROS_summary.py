'''
DRAFT

Changes this branch: Added different category adjustment for mines, the hybrid adjustment.

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

import os, time, arcpy, csv, logging, datetime


#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
log_tag = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M')
log_file = os.path.join(os.path.dirname(__file__), 'ROS_LogFile_{}.log'.format(log_tag))
logging.basicConfig(level=logging.DEBUG,
    format='%(asctime)s:%(levelname)-4s:\t%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S ',
    filename=log_file,
    filemode='a') #'a' appends to an existing file while 'w' overwrites anything already in the file
logging.info('START LOGGING')
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
csv_name = 'ROS_layers.csv'
layers = os.path.join(os.path.dirname(os.path.realpath(__file__)), csv_name) # the CSV must be in the same folder as the script
paths_dict = {} # the dictionary holds the layer's nickname and file path from the CSV
mines_list = [] # a list to hold the layers which will be used to check for the presence of mines
with open(layers, 'r') as table: # read the csv 
    reader = csv.reader(table)
    next(reader, None) # this skips the first row - the column names
    for row in reader:
        a, b = row # CSV columns are laid out left to right: layer nickname (a) then layer path (b)
        paths_dict[a]=b
        if 'mine' in a: # check for keyword 'mine' in the nickname (column a of the csv)
            mines_list.append(b)
            print(a, b)           
workspace = paths_dict['workspace']
arcpy.env.workspace = workspace
arcpy.env.overwriteOutput = True
logging.info('CSV read successfully')
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# include function to check for presence of mines and adjust the field as required 
# function called near end of ROS_summary
def mine_check(in_layer, out_layer, in_field, in_dif: int, in_check: list): # eg Pass to function: ROS assessment output layer, name of the field to update, value to set the field to, the number of categories to change an AU neighboring a mine, the mines layer to check for presence
    try:
        logging.info('Adjusting ROS category of AUs for mine heavy adjustment')
        arcpy.conversion.FeatureClassToFeatureClass(in_layer, workspace, out_layer) # make a new layer to preserve the results of ROS assessment
        new_field = 'prev_ROS_code' # add a field to store what the ROS code was before being changed by a category - also works to check whether or not the feature has had its ROS code changed already
        arcpy.management.AddField(out_layer, new_field, 'TEXT', field_is_nullable = True) # field will be null for any AUs that do not have a mine or border an AU with a mine
        new_field2 = 'ROS_difference'
        arcpy.management.AddField(out_layer, new_field2, 'SHORT', field_is_nullable = True) 
        with arcpy.da.UpdateCursor(out_layer, [new_field2]) as cursor:
            for row in cursor:
                row[0] = 0
                cursor.updateRow(row)
        ROS_dict = { # dictionary of the ROS codes assigned to an int in increasing order of recreation opportunity (ie higher the key, the 'better' the ROS code)
            1: 'R',
            2: 'RM',
            3: 'RN',
            4: 'SPM',
            5: 'SPNM',
            6: 'P'
        } 
        num_dict = {
            'R': 1,
            'RM': 2,
            'RN': 3,
            'SPM': 4,
            'SPNM': 5,
            'P': 6
        }
        counter=0
        for mine in in_check:
            mine_sel = arcpy.management.SelectLayerByLocation(out_layer, 'INTERSECT', mine, selection_type='NEW_SELECTION') # select the AU features that contain one of these mine features. These AUs and their neighbors need to be brought down by one code level
            with arcpy.da.UpdateCursor(mine_sel, [in_field, new_field, new_field2]) as cursor:
                for row in cursor:
                    if not row[1]:
                        row[1] = row[0]
                        row[0] = ROS_dict[1]
                        row[2] = num_dict[row[1]] - num_dict[row[0]]
                        cursor.updateRow(row)
                        counter+=1
            boundary_sel = arcpy.management.SelectLayerByLocation(out_layer, "BOUNDARY_TOUCHES", mine_sel, selection_type='NEW_SELECTION') # now add to the selection all the AU features that share a boundary with the already selected features
            boundary_sel = arcpy.management.SelectLayerByLocation(boundary_sel, "ARE_IDENTICAL_TO", mine_sel, selection_type='REMOVE_FROM_SELECTION')
            
            with arcpy.da.UpdateCursor(boundary_sel, [in_field, new_field, new_field2]) as cursor: # change the AUs that have a mine in them and their neighbors to ROS one ROS code lower
                for row in cursor:
                    if not row[1]: # ensure that the feature has not already been updated
                        for key, code in ROS_dict.items(): # this nested for loop is not good practice. I'm not quite sure how else to get the key out of ROS_dict if it's not the item in the dict being evaluated
                            if row[0] == code: # only 1 of the 6 items in the dict are necessary
                                row[1] = row[0] # update the new_field to store what the previous ROS code was
                                if key >= 2:
                                    row[0] =  ROS_dict[key-in_dif] # set the predominant ROS code field to the next lower code
                                else:
                                    row[0] = ROS_dict[1] # there is no key lower than 1
                                row[2] = num_dict[row[1]] - num_dict[row[0]]
                                counter+=1
                        cursor.updateRow(row)
        logging.info('{} features updated for mines'.format(counter))
        print('{} features updated for mines'.format(counter))
    except:
        print('Unable to complete mine_check function')
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# include alternate function to check for presence of mines and adjust the field as required
# function called near end of ROS_summary
def hybrid_check(in_layer, out_layer, in_field, in_dif: int, in_check: list): # eg Pass to function: ROS assessment output layer, name of the field to update, value to set the field to, the number of categories to change an AU neighboring a mine, the mines layer to check for presence
    try:
        logging.info('Updating ROS categories for AU for hybrid mine adjustment')
        arcpy.conversion.FeatureClassToFeatureClass(in_layer, workspace, out_layer) # make a new layer to preserve the results of ROS assessment
        new_field = 'prev_ROS_code' # add a field to store what the ROS code was before being changed by a category - also works to check whether or not the feature has had its ROS code changed already
        arcpy.management.AddField(out_layer, new_field, 'TEXT', field_is_nullable = True) # field will be null for any AUs that do not have a mine or border an AU with a mine
        new_field2 = 'ROS_difference'
        arcpy.management.AddField(out_layer, new_field2, 'SHORT', field_is_nullable = True) 
        ROS_dict = { # dictionary of the ROS codes assigned to an int in increasing order of recreation opportunity (ie higher the key, the 'better' the ROS code)
            1: 'R',
            2: 'RM',
            3: 'RN',
            4: 'SPM',
            5: 'SPNM',
            6: 'P'
        } 
        num_dict = {
            'R': 1,
            'RM': 2,
            'RN': 3,
            'SPM': 4,
            'SPNM': 5,
            'P': 6
        }
        counter = 0
        for mine in in_check:
            if 'TRIM' in mine:
                attr_sel = arcpy.management.SelectLayerByAttribute(mine, selection_type='NEW_SELECTION', where_clause="FEATURE_TYPE IN ('mine', 'mineOpenPit')")
                mine_sel = arcpy.management.SelectLayerByLocation(out_layer, 'INTERSECT', attr_sel, selection_type='NEW_SELECTION') # select the AU features that contain one of these mine features. These AUs and their neighbors need to be brought down by one code level
                with arcpy.da.UpdateCursor(mine_sel, [in_field, new_field, new_field2]) as cursor: # change the AUs that have a mine in them and their neighbors to ROS one ROS code lower
                    for row in cursor:
                        if not row[1]: # ensure that the feature has not already been updated
                            for key, code in ROS_dict.items(): # this nested for loop is not good practice. I'm not quite sure how else to get the key out of ROS_dict if it's not the item in the dict being evaluated
                                if row[0] == code: # only 1 of the 6 items in the dict are necessary
                                    row[1] = row[0] # update the new_field to store what the previous ROS code was
                                    if key >= 2:
                                        row[0] =  ROS_dict[key-in_dif] # set the predominant ROS code field to the next lower code
                                    else:
                                        row[0] = ROS_dict[1] # there is no key lower than 1
                                    row[2] = num_dict[row[1]] - num_dict[row[0]]
                                    counter+=1 
                            cursor.updateRow(row)         
            else:
                mine_sel = arcpy.management.SelectLayerByLocation(out_layer, 'INTERSECT', mine, selection_type='NEW_SELECTION') # select the AU features that contain one of these mine features. These AUs and their neighbors need to be brought down by one code level
                with arcpy.da.UpdateCursor(mine_sel, [in_field, new_field, new_field2]) as cursor:
                    for row in cursor:
                        if not row[1]:
                            row[1] = row[0]
                            row[0] = ROS_dict[1]
                            row[2] = int(num_dict[row[1]]) - int(num_dict[row[0]])
                            cursor.updateRow(row)
                            counter+=1
                boundary_sel = arcpy.management.SelectLayerByLocation(out_layer, "BOUNDARY_TOUCHES", mine_sel, selection_type='NEW_SELECTION') # now add to the selection all the AU features that share a boundary with the already selected features
                boundary_sel = arcpy.management.SelectLayerByLocation(boundary_sel, "ARE_IDENTICAL_TO", mine_sel, selection_type='REMOVE_FROM_SELECTION')
                with arcpy.da.UpdateCursor(boundary_sel, [in_field, new_field, new_field2]) as cursor: # change the AUs that have a mine in them and their neighbors to ROS one ROS code lower
                    for row in cursor:
                        if not row[1]: # ensure that the feature has not already been updated
                            for key, code in ROS_dict.items(): # this nested for loop is not good practice. I'm not quite sure how else to get the key out of ROS_dict if it's not the item in the dict being evaluated
                                if row[0] == code: # only 1 of the 6 items in the dict are necessary
                                    row[1] = row[0] # update the new_field to store what the previous ROS code was
                                    if key >= 2:
                                        row[0] =  ROS_dict[key-in_dif] # set the predominant ROS code field to the next lower code
                                    else:
                                        row[0] = ROS_dict[1] # there is no key lower than 1
                                    old = row[1] 
                                    new = row[0]   
                                    row[2] = num_dict[old]-num_dict[new]
                                    counter+=1 
                            cursor.updateRow(row)
        logging.info('{} features updated'.format(counter))
        print('{} features updated for hybrid adjustment'.format(counter))
    except:
        print('Unable to complete mine_check function')
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
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
    #----------------------------------------------------------------
    # Do the ROS assessment
    try:
        ros_clip = 'ROS_{}_clip_{}'.format(area_name, tag)
        arcpy.analysis.PairwiseClip(in_ROS, fwa_export, ros_clip) # clip the ROS to the copy of the AU layer
        category_list = set([row[0] for row in arcpy.da.SearchCursor(ros_clip, ['REC_OPP_SPECTRUM_CODE'])]) # list of ROS categories using list comprehension
        outputs_list = []
        for cat in category_list: #Approx 40 seconds per iteration
            field_ha = '{}_Area_HA'.format(cat)
            field_pct = '{}_Area_PCNT'.format(cat) # Add these fields for each category type
            outputs_list.append(field_pct)
            arcpy.management.AddField(fwa_export, field_ha, "FLOAT", field_is_nullable='TRUE')
            arcpy.management.AddField(fwa_export, field_pct, "FLOAT", field_is_nullable='TRUE')
            ros_sel = arcpy.management.SelectLayerByAttribute(ros_clip, 'NEW_SELECTION', """REC_OPP_SPECTRUM_CODE = '{}'""".format(cat))
            if int(str(arcpy.management.GetCount(ros_sel))) > 0: 
                out_sum = r'FWA_AU_ROS_{}'.format(cat) #non static output name to be used later to update fwa_export
                arcpy.analysis.SummarizeWithin(fwa_export, ros_sel, out_sum, 'KEEP_ALL', '', 'ADD_SHAPE_SUM', 'HECTARES')
                scursor = [row[0] for row in arcpy.da.SearchCursor(out_sum, ("sum_Area_HECTARES"))]
                ucursor = arcpy.da.UpdateCursor(fwa_export, ['AREA_HA', field_ha, field_pct]) # ucursor and scursor are the same length, so the update cursor in tandem with the search cursor works
                i=0
                for row in ucursor:      
                    row[1] = round(scursor[i], 2)
                    row[2] = round(float(scursor[i])/float(row[0])*100, 2)
                    i+=1
                    ucursor.updateRow(row)
                arcpy.management.Delete(out_sum)
                del scursor, ucursor
            else:
                print('No area overlap for {}'.format(out_sum)) # Just in case that an entire ROS category is not in the AOI, can skip the steps and set the fields to 0
                logging.info('No area overlap for {}'.format(out_sum))
                ucursor = arcpy.da.UpdateCursor(fwa_export, [field_ha, field_pct]) 
                for row in ucursor:      
                    row[0] = 0.0
                    row[1] = 0.0
                    ucursor.updateRow(row)
                arcpy.management.Delete(out_sum)
                del scursor, ucursor
            logging.info('{} iteration completed'.format(cat))
            print('{} iteration completed'.format(cat))
    except:
        print('\nUnable to complete ROS assessment steps')
        print(arcpy.GetMessages())
        logging.error(arcpy.GetMessages())
    # -------------------------------------------------------------------------------------------------
    # clunky way of extracting the ROS category from the percent area field that was calculated above. Possible to use a variable to hold the highest area within the category loop?
    # Use search cursor to get the pcnt areas for each fow in fwa_export. Sort list of percent areas to put highest area first. 
    # Use a dictionary that was created before sorting list to match the ROS cat with the percent area even after soring. No search the dict by largest area to extract the ROS category
    try:
        new_field = 'Predominant_ROS_cat'
        arcpy.management.AddField(fwa_export, new_field, 'TEXT', field_is_nullable=True)
        new_field2 = 'ROS_num'
        arcpy.management.AddField(fwa_export, new_field2, 'SHORT', field_is_nullable=True)
        outputs_list.insert(0, new_field) # Can specify the index in list to insert the object using list.INSERT(index, element). Unlike list.APPEND() which just tacks on the new list element at the end
        outputs_list.insert(1, new_field2)
        num_dict = {
            'R':1,
            'RM':2,
            'RN':3,
            'SPM':4,
            'SPNM':5,
            'P':6
        }
        successcount = 0
        iteration = 0
        with arcpy.da.UpdateCursor(fwa_export, outputs_list) as cursor:
            for row in cursor:
                iteration += 1
                fields_dict = {}
                sorted_list = row[2:] # need to compare the ROS cat area % to find the category with the largest %
                for i in range(2, len(outputs_list)): # 
                    fields_dict[outputs_list[i]] = row[i] # need to add field, percent pairs into the dictionary. If not in dictionary, cannot get the ROS category out of the area percent
                sorted_list.sort(reverse=True) # Sort list in descending order - ie largest % first
                search_val = sorted_list[0] # Need to do this because dictionaries are not ordered - for each par in the dictionary, we will compare values to this search_val (the greatest % of ROS cat) 
                for field, pct in fields_dict.items():
                    if pct == search_val:
                        row[0] = field[:-10] # Assign the new_field to the ROS category that's the greatest % of the AU being evaluated. The entire field string is like 'RN_Area_PCNT', so slice off the last 10 chars to only have the ROS category code remaining
                        # row[1] = num_dict[field[:-10]]
                        successcount+=1
                        break
                    else:
                        pass
                cursor.updateRow(row)
                del fields_dict
        print('{} of {} AUs assigned ROS category'.format(successcount, iteration))
        logging.info('{} of {} AUs assigned ROS category'.format(successcount, iteration))
        hybrid_layer = '{}_hybrid_adjustment'.format(fwa_export.rsplit('\\', 1)[-1]) 
        hybrid_check(fwa_export, hybrid_layer, new_field, 1, mines_list)
        mine_layer = '{}_mine_adjustment'.format(fwa_export.rsplit('\\', 1)[-1])
        mine_check(fwa_export, mine_layer, new_field, 1, mines_list)
        arcpy.management.Delete(ros_clip)
        totalTime = time.strftime("%H:%M:%S",time.gmtime(time.time() - startTime))
        print('\nThe ROS assessment took {} to run'.format(totalTime))
        logging.info('FUNCTION COMPLETE')
    except:
        print('\nUnable to complete greatest area ROS category assignment for assessment watershed')
        print(arcpy.GetMessages())
        logging.error(arcpy.GetMessages())
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# Call the function on the layers from paths_dict        
ROS_summary(paths_dict['AOI'], paths_dict['ROS'], paths_dict['AU'])