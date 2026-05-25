import requests
import json
import os
from dotenv import load_dotenv
import time
import pymysql.cursors
import citizenphil as cp
import tmdb_functions as tf
from datetime import datetime, timedelta
import csv
import pandas as pd
import re
from SPARQLWrapper import SPARQLWrapper, SPARQLExceptions, JSON, POST

# Load .env file 
load_dotenv()

strwikidatauseragent = os.getenv("WIKIMEDIA_USER_AGENT")
print("strwikidatauseragent",strwikidatauseragent)

strprocessesexecutedprevious = cp.f_getservervariable("strsparqlcrawlerprocessesexecuted",0)
strprocessesexecuteddesc = "List of processes executed in the Wikidata SPARQL crawler"
cp.f_setservervariable("strsparqlcrawlerprocessesexecutedprevious",strprocessesexecutedprevious,strprocessesexecuteddesc + " (previous execution)",0)
strprocessesexecuted = ""
cp.f_setservervariable("strsparqlcrawlerprocessesexecuted",strprocessesexecuted,strprocessesexecuteddesc,0)

try:
    conn = cp.f_getconnection()
    with conn:
        with conn.cursor() as cursor:
            cursor3 = conn.cursor()
            # Start timing the script execution
            start_time = time.time()
            strnow = datetime.now(cp.paris_tz).strftime("%Y-%m-%d %H:%M:%S")
            cp.f_setservervariable("strsparqlcrawlerstartdatetime",strnow,"Date and time of the last start of the Wikidata SPARQL crawler",0)
            strtotalruntimedesc = "Total runtime of the Wikidata SPARQL crawler"
            strtotalruntimeprevious = cp.f_getservervariable("strsparqlcrawlertotalruntime",0)
            cp.f_setservervariable("strsparqlcrawlertotalruntimeprevious",strtotalruntimeprevious,strtotalruntimedesc + " (previous execution)",0)
            strtotalruntime = "RUNNING"
            cp.f_setservervariable("strsparqlcrawlertotalruntime",strtotalruntime,strtotalruntimedesc,0)

            # Retrieving instance of values for persons (humans) used in Wikidata Sparql queries
            strsparqlpersoninstanceof = cp.f_getservervariable("strsparqlaltcrawlerpersoninstanceof",0)
            if strsparqlpersoninstanceof == "":
                strsparqlpersoninstanceof = "Q5"
                cp.f_setservervariable("strsparqlaltcrawlerpersoninstanceof",strsparqlpersoninstanceof,"Instances of values for persons (humans) used in Wikidata Sparql queries",0)
            # Retrieving instance of values for movies used in Wikidata Sparql queries
            strsparqlmovieinstanceof = cp.f_getservervariable("strsparqlaltcrawlermovieinstanceof",0)
            if strsparqlmovieinstanceof == "":
                strsparqlmovieinstanceof = "Q11424 Q202866 Q226730 Q24862 Q20650540 Q506240 Q17517379"
                cp.f_setservervariable("strsparqlaltcrawlermovieinstanceof",strsparqlmovieinstanceof,"Instances of values for movies used in Wikidata Sparql queries",0)
            # Retrieving instance of values for series used in Wikidata Sparql queries
            strsparqlserieinstanceof = cp.f_getservervariable("strsparqlaltcrawlerserieinstanceof",0)
            if strsparqlserieinstanceof == "":
                strsparqlserieinstanceof = "Q5398426 Q1259759 Q117467246 Q63952888 Q15416"
                cp.f_setservervariable("strsparqlaltcrawlerserieinstanceof",strsparqlserieinstanceof,"Instances of values for series used in Wikidata Sparql queries",0)

            #arrwikidatascope = {107: 'person aliases', 106: 'movie aliases'}
            arrwikidatascope = {100: 'property', 109: 'item add', 112: 'move item to person', 115: 'person properties VIP', 105: 'person properties', 104: 'movie properties', 114: 'serie properties', 116: 'season properties', 117: 'episode properties', 118: 't2s collection properties', 119: 't2s character properties', 120: 't2s award properties', 121: 't2s nomination properties', 122: 't2s topic properties', 123: 't2s technical properties', 124: 't2s group properties', 125: 't2s movement properties', 126: 't2s list properties', 127: 't2s death properties'}
            #if strnow.startswith("2026-05-24"):
            #    arrwikidatascope = {100: 'property', 116: 'season properties', 117: 'episode properties', 114: 'serie properties', 109: 'item add', 112: 'move item to person', 115: 'person properties VIP', 105: 'person properties', 104: 'movie properties'}

            for intindex,strcontent in arrwikidatascope.items():
                strcurrentprocess = f"{intindex}: processing Wikidata " + strcontent + " data using SPARQL"
                strprocessesexecuted += str(intindex) + ", "
                cp.f_setservervariable("strsparqlcrawlerprocessesexecuted",strprocessesexecuted,strprocessesexecuteddesc,0)
                print(strcurrentprocess)
                datnow = datetime.now(cp.paris_tz)
                delta30 = timedelta(days=30)
                datjminus30 = datnow - delta30
                strdatjminus30 = datjminus30.strftime("%Y-%m-%d")
                delta100 = timedelta(days=100)
                datjminus100 = datnow - delta100
                strdatjminus100 = datjminus100.strftime("%Y-%m-%d")
                if intindex == 100:
                    # Wikidata properties data download
                    cp.f_setservervariable("strsparqlcrawlerpropertiescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    time.sleep(90)
                    # Define the SPARQL query
                    # Explicit per-language OPTIONAL clauses pull EN + FR label/description in
                    # one row each, replacing the single wikibase:label service that only
                    # returned one language. Properties missing a translation simply leave
                    # those vars unbound, so the OPTIONALs are required.
                    strsparqlquery = ""
                    strsparqlquery += "SELECT ?property ?propertyLabel ?propertyDescription ?propertyLabelFr ?propertyDescriptionFr WHERE { "
                    strsparqlquery += "?property a wikibase:Property . "
                    strsparqlquery += "OPTIONAL { ?property rdfs:label ?propertyLabel FILTER(LANG(?propertyLabel) = \"en\") } "
                    strsparqlquery += "OPTIONAL { ?property schema:description ?propertyDescription FILTER(LANG(?propertyDescription) = \"en\") } "
                    strsparqlquery += "OPTIONAL { ?property rdfs:label ?propertyLabelFr FILTER(LANG(?propertyLabelFr) = \"fr\") } "
                    strsparqlquery += "OPTIONAL { ?property schema:description ?propertyDescriptionFr FILTER(LANG(?propertyDescriptionFr) = \"fr\") } "
                    strsparqlquery += "} "
                    strsparqlquery += "ORDER BY ?property "
                    # Initialize the SPARQL wrapper
                    sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                    # Set the query and return format
                    print(strsparqlquery)
                    sparql.setQuery(strsparqlquery)
                    sparql.setReturnFormat(JSON)
                    sparql.setMethod(POST)
                    # Execute the query and convert the results
                    try:
                        query_result = sparql.query()
                        results = query_result.convert()
                        df = pd.json_normalize(results['results']['bindings'])
                        if not df.empty:
                            for index, row in df.iterrows():
                                stritem = row['property.value']
                                # Compute strwikidataid
                                strwikidataid = ""
                                strwikidataid = stritem.split('/')[-1]
                                cp.f_setservervariable("strsparqlcrawlerpropertiescurrentvalue",strwikidataid,"Current value in the current Wikidata SPARQL crawler",0)
                                cp.f_setservervariable("strsparqlcrawlerpropertieswikidataid",strwikidataid,"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                                # Compute strlabel
                                strlabel = ""
                                if 'propertyLabel.value' in row:
                                    if row['propertyLabel.value']:
                                        if not pd.isna(row['propertyLabel.value']):
                                            strlabel = row['propertyLabel.value']
                                            # reject any label that looks like a Wikidata ID
                                            if re.match(r'^[QPL]\d+$', strlabel):
                                                strlabel = ""
                                # Compute strdescription
                                strdescription = ""
                                if 'propertyDescription.value' in row:
                                    if row['propertyDescription.value']:
                                        if not pd.isna(row['propertyDescription.value']):
                                            strdescription = row['propertyDescription.value']
                                # Compute strlabelfr
                                strlabelfr = ""
                                if 'propertyLabelFr.value' in row:
                                    if row['propertyLabelFr.value']:
                                        if not pd.isna(row['propertyLabelFr.value']):
                                            strlabelfr = row['propertyLabelFr.value']
                                            # reject any label that looks like a Wikidata ID
                                            if re.match(r'^[QPL]\d+$', strlabelfr):
                                                strlabelfr = ""
                                # Compute strdescriptionfr
                                strdescriptionfr = ""
                                if 'propertyDescriptionFr.value' in row:
                                    if row['propertyDescriptionFr.value']:
                                        if not pd.isna(row['propertyDescriptionFr.value']):
                                            strdescriptionfr = row['propertyDescriptionFr.value']
                                strmessage = f"{strwikidataid} '{strlabel}' {strdescription} | FR '{strlabelfr}' {strdescriptionfr}"
                                print(strmessage)
                                arrmoviecouples = {}
                                arrmoviecouples["ID_PROPERTY"] = strwikidataid
                                arrmoviecouples["LABEL"] = strlabel
                                arrmoviecouples["DESCRIPTION"] = strdescription
                                arrmoviecouples["LABEL_FR"] = strlabelfr
                                arrmoviecouples["DESCRIPTION_FR"] = strdescriptionfr
                                strsqltablename = "T_WC_WIKIDATA_PROPERTY"
                                strsqlupdatecondition = f"ID_PROPERTY = '{strwikidataid}'"
                                cp.f_sqlupdatearray(strsqltablename,arrmoviecouples,strsqlupdatecondition,1)
                    except SPARQLExceptions.EndPointInternalError as e:
                        print(f"Internal Server Error: {e}")
                    except SPARQLExceptions.QueryBadFormed as e:
                        print(f"Badly Formed Query: {e}")
                    except SPARQLExceptions.EndPointNotFound as e:
                        print(f"Endpoint Not Found: {e}")
                    except Exception as e:
                        print(f"An error occurred: {e}")
                        lngretryafter = 60
                        print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                        time.sleep(lngretryafter)
                if intindex == 103:
                    # Series data download
                    lngoffset = -1
                    # Year begin for the query
                    lngyearbegin = 2028
                    #lngyearbegin = 2018
                    #lngyearbegin = 2115 for 100 years
                    #lngyearbegin = 1943
                    # Year end for the query
                    lngyearend = 1894
                    #lngyearend = 2115
                    #lngyearend = 1943
                    lngyearquery = lngyearbegin
                    intencore = True
                    strwikidataidprev = ""
                    strgenrelist = ""
                    strcolorlist = ""
                    while intencore:
                        cp.f_setservervariable("strsparqlcrawlerseriescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                        cp.f_setservervariable("strsparqlcrawlerseriescurrentvalue",str(lngyearquery),"Current year in the Wikidata SPARQL crawler serie process",0)
                        strnow = datetime.now(cp.paris_tz).strftime("%Y%m%d-%H%M%S")
                        #time.sleep(90)
                        intencore = False
                    
                if intindex == 104:
                    # Wikidata movie properties data download
                    cp.f_setservervariable("strsparqlcrawlermoviepropertiescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT DISTINCT T_WC_TMDB_MOVIE.ID_WIKIDATA, T_WC_TMDB_MOVIE.TITLE, T_WC_TMDB_MOVIE.ORIGINAL_TITLE, T_WC_TMDB_MOVIE.DAT_RELEASE, T_WC_TMDB_MOVIE.ID_MOVIE, T_WC_TMDB_MOVIE.ID_IMDB, T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating "
                    strsql += "FROM T_WC_TMDB_MOVIE "
                    #strsql += "INNER JOIN T_WC_WIKIDATA_MOVIE_V1 ON T_WC_TMDB_MOVIE.ID_WIKIDATA = T_WC_WIKIDATA_MOVIE_V1.ID_WIKIDATA "
                    strsql += "LEFT JOIN T_WC_IMDB_MOVIE_RATING_IMPORT ON T_WC_TMDB_MOVIE.ID_IMDB = T_WC_IMDB_MOVIE_RATING_IMPORT.tconst "
                    strsql += "WHERE T_WC_TMDB_MOVIE.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_MOVIE.ID_WIKIDATA <> '' "
                    strsql += "AND T_WC_TMDB_MOVIE.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                    strsql += "AND T_WC_TMDB_MOVIE.ID_WIKIDATA LIKE 'Q%' "
                    strsql += "AND (T_WC_TMDB_MOVIE.TIM_WIKIDATA_COMPLETED IS NULL OR T_WC_TMDB_MOVIE.TIM_WIKIDATA_COMPLETED < '" + strdatjminus30 + "') "
                    #strsql += "AND (T_WC_TMDB_MOVIE.ID_MOVIE IN ( "
                    #strsql += "SELECT ID_MOVIE FROM T_WC_TMDB_MOVIE_LIST WHERE ID_LIST IN ( "
                    #strsql += "SELECT ID_LIST FROM T_WC_TMDB_LIST WHERE DELETED = 0 AND USE_FOR_TAGGING >= 1 "
                    #strsql += ") "
                    #strsql += ") "
                    #strsql += "OR (T_WC_WIKIDATA_MOVIE_V1.ID_CRITERION IS NOT NULL AND T_WC_WIKIDATA_MOVIE_V1.ID_CRITERION <> 0) "
                    #strsql += ") "
                    #strsql += "AND T_WC_TMDB_MOVIE.ID_WIKIDATA = 'Q1199628' "
                    #strsql += "ORDER BY T_WC_TMDB_MOVIE.ID_MOVIE "
                    strsql += "ORDER BY T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating DESC "
                    strsql += "LIMIT 10000 "
                    # strsql += "LIMIT 1 "
                    if strsql != "":
                        print(strsql)
                        #cp.f_setservervariable("strsparqlcrawlercurrentsql",strsql,"Current SQL query in the SPARQL Wikidata crawler",0)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        # Print per-item context so logs still show what's being processed,
                        # then group ids into 500-id batches and issue one POST per batch.
                        for row3 in results:
                            lngid = row3['ID_MOVIE']
                            strwikidataid = row3['ID_WIKIDATA']
                            strmovietitle = row3['TITLE']
                            strmovieoriginaltitle = row3['ORIGINAL_TITLE']
                            datrelease = row3['DAT_RELEASE']
                            stryearrelease = ""
                            if datrelease:
                                stryearrelease = datrelease.strftime("%Y")
                            dblimdbrating = row3['averageRating']
                            strmessage = f"{lngid} {strmovietitle} ({stryearrelease})"
                            if strmovietitle != strmovieoriginaltitle:
                                strmessage += f" AKA {strmovieoriginaltitle}"
                            strmessage += f" {dblimdbrating} {strwikidataid}"
                            print(strmessage)
                        # Batch WDQS calls instead of one HTTP round-trip per movie:
                        # a single VALUES ?item { wd:Q1 wd:Q2 ... } query returns many items at once,
                        # cuts rate-limit pressure by ~lngbatchsize, and avoids the 1000s 429 back-off loop.
                        # The ?p/?statement/?value claim expansion explodes per item, so keep
                        # the batch small to stay under the WDQS 60s timeout.
                        arrrowsall = list(results)
                        lngbatchsize = 50
                        for lngi in range(0, len(arrrowsall), lngbatchsize):
                            arrrowsbatch = arrrowsall[lngi:lngi + lngbatchsize]
                            arrbatch = [r['ID_WIKIDATA'] for r in arrrowsbatch]
                            strbatchidswd = " ".join([f"wd:{x}" for x in arrbatch])
                            strbatchlabel = f"{arrbatch[0]}..{arrbatch[-1]} ({len(arrbatch)} ids)"
                            cp.f_setservervariable("strsparqlcrawlermoviepropertiescurrentvalue",strbatchlabel,"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawlermoviepropertieswikidataid",arrbatch[-1],"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            print(f"batch {lngi // lngbatchsize + 1}: {strbatchlabel}")
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                # Define the SPARQL query
                                strlang = "en"
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?item ?property ?propertyLabel ?value ?valueLabel WHERE { "
                                strsparqlquery += "VALUES ?item { " + strbatchidswd + " } "
                                strsparqlquery += "  ?item ?p ?statement . "
                                strsparqlquery += "  ?statement ?ps ?value . "
                                strsparqlquery += "  ?property wikibase:claim ?p . "
                                strsparqlquery += "  ?property rdfs:label ?propertyLabel FILTER(LANG(?propertyLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "  ?value rdfs:label ?valueLabel FILTER(LANG(?valueLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "} "
                                strsparqlquery += "ORDER BY ?item ?property ?propertyLabel "
                                # Initialize the SPARQL wrapper
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                # Set the query and return format
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                # Execute the query and convert the results
                                try:
                                    query_result = sparql.query()
                                    results_sparql = query_result.convert()
                                    intencore = False
                                    df = pd.json_normalize(results_sparql['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stritem = row['item.value']
                                            strwikidataid = stritem.split('/')[-1]
                                            strproperty = row['property.value']
                                            # Compute strpropertyid
                                            strpropertyid = ""
                                            strpropertyid = strproperty.split('/')[-1]
                                            stritemid = ""
                                            if 'value.value' in row:
                                                if row['value.value']:
                                                    if not pd.isna(row['value.value']):
                                                        stritemvalue = row['value.value']
                                                        stritemid = stritemvalue.split('/')[-1]
                                            arritemcouples = {}
                                            arritemcouples["ID_WIKIDATA"] = strwikidataid
                                            arritemcouples["ID_PROPERTY"] = strpropertyid
                                            arritemcouples["ID_ITEM"] = stritemid
                                            strsqltablename = "T_WC_WIKIDATA_ITEM_PROPERTY"
                                            strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}' AND ID_PROPERTY = '{strpropertyid}' AND ID_ITEM = '{stritemid}'"
                                            cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                            # Mark every movie in the batch as completed — items with no
                            # properties simply don't appear in the SPARQL result set.
                            for row3 in arrrowsbatch:
                                tf.f_tmdbmoviesetwikidatacompleted(row3['ID_MOVIE'])
                            
                if intindex == 114:
                    # Wikidata serie properties data download
                    cp.f_setservervariable("strsparqlcrawlerseriepropertiescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT DISTINCT T_WC_TMDB_SERIE.ID_WIKIDATA, T_WC_TMDB_SERIE.TITLE, T_WC_TMDB_SERIE.ORIGINAL_TITLE, T_WC_TMDB_SERIE.FIRST_AIR_YEAR, T_WC_TMDB_SERIE.LAST_AIR_YEAR, T_WC_TMDB_SERIE.ID_SERIE, T_WC_TMDB_SERIE.ID_IMDB, T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating "
                    strsql += "FROM T_WC_TMDB_SERIE "
                    #strsql += "INNER JOIN T_WC_WIKIDATA_SERIE_V1 ON T_WC_TMDB_SERIE.ID_WIKIDATA = T_WC_WIKIDATA_SERIE_V1.ID_WIKIDATA "
                    strsql += "LEFT JOIN T_WC_IMDB_MOVIE_RATING_IMPORT ON T_WC_TMDB_SERIE.ID_IMDB = T_WC_IMDB_MOVIE_RATING_IMPORT.tconst "
                    strsql += "WHERE T_WC_TMDB_SERIE.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_SERIE.ID_WIKIDATA <> '' "
                    strsql += "AND T_WC_TMDB_SERIE.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                    strsql += "AND T_WC_TMDB_SERIE.ID_WIKIDATA LIKE 'Q%' "
                    strsql += "AND (T_WC_TMDB_SERIE.TIM_WIKIDATA_COMPLETED IS NULL OR T_WC_TMDB_SERIE.TIM_WIKIDATA_COMPLETED < '" + strdatjminus30 + "') "
                    #strsql += "AND (T_WC_TMDB_SERIE.ID_SERIE IN ( "
                    #strsql += "SELECT ID_SERIE FROM T_WC_TMDB_SERIE_LIST WHERE ID_LIST IN ( "
                    #strsql += "SELECT ID_LIST FROM T_WC_TMDB_LIST WHERE DELETED = 0 AND USE_FOR_TAGGING >= 1 "
                    #strsql += ") "
                    #strsql += ") "
                    #strsql += "OR (T_WC_WIKIDATA_MOVIE_V1.ID_CRITERION IS NOT NULL AND T_WC_WIKIDATA_MOVIE_V1.ID_CRITERION <> 0) "
                    #strsql += ") "
                    #strsql += "AND T_WC_TMDB_MOVIE.ID_WIKIDATA = 'Q1199628' "
                    #strsql += "ORDER BY T_WC_TMDB_MOVIE.ID_MOVIE "
                    strsql += "ORDER BY T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating DESC "
                    strsql += "LIMIT 10000 "
                    # strsql += "LIMIT 1 "
                    if strsql != "":
                        print(strsql)
                        #cp.f_setservervariable("strsparqlcrawlercurrentsql",strsql,"Current SQL query in the SPARQL Wikidata crawler",0)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        # Print per-item context so logs still show what's being processed,
                        # then group ids into 500-id batches and issue one POST per batch.
                        for row3 in results:
                            lngid = row3['ID_SERIE']
                            strwikidataid = row3['ID_WIKIDATA']
                            strserieoriginaltitle = row3['ORIGINAL_TITLE']
                            strfirstairyear = row3['FIRST_AIR_YEAR']
                            strlastairyear = row3['LAST_AIR_YEAR']
                            dblimdbrating = row3['averageRating']
                            strmessage = f"{lngid} {strserieoriginaltitle} ({strfirstairyear}-{strlastairyear})"
                            strmessage += f" {dblimdbrating} {strwikidataid}"
                            print(strmessage)
                        # Batch WDQS calls instead of one HTTP round-trip per serie:
                        # a single VALUES ?item { wd:Q1 wd:Q2 ... } query returns many items at once,
                        # cuts rate-limit pressure by ~lngbatchsize, and avoids the 1000s 429 back-off loop.
                        # The ?p/?statement/?value claim expansion explodes per item, so keep
                        # the batch small to stay under the WDQS 60s timeout.
                        arrrowsall = list(results)
                        lngbatchsize = 50
                        for lngi in range(0, len(arrrowsall), lngbatchsize):
                            arrrowsbatch = arrrowsall[lngi:lngi + lngbatchsize]
                            arrbatch = [r['ID_WIKIDATA'] for r in arrrowsbatch]
                            strbatchidswd = " ".join([f"wd:{x}" for x in arrbatch])
                            strbatchlabel = f"{arrbatch[0]}..{arrbatch[-1]} ({len(arrbatch)} ids)"
                            cp.f_setservervariable("strsparqlcrawlerseriepropertiescurrentvalue",strbatchlabel,"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawlerseriepropertieswikidataid",arrbatch[-1],"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            print(f"batch {lngi // lngbatchsize + 1}: {strbatchlabel}")
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                # Define the SPARQL query
                                strlang = "en"
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?item ?property ?propertyLabel ?value ?valueLabel WHERE { "
                                strsparqlquery += "VALUES ?item { " + strbatchidswd + " } "
                                strsparqlquery += "  ?item ?p ?statement . "
                                strsparqlquery += "  ?statement ?ps ?value . "
                                strsparqlquery += "  ?property wikibase:claim ?p . "
                                strsparqlquery += "  ?property rdfs:label ?propertyLabel FILTER(LANG(?propertyLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "  ?value rdfs:label ?valueLabel FILTER(LANG(?valueLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "} "
                                strsparqlquery += "ORDER BY ?item ?property ?propertyLabel "
                                # Initialize the SPARQL wrapper
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                # Set the query and return format
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                # Execute the query and convert the results
                                try:
                                    query_result = sparql.query()
                                    results_sparql = query_result.convert()
                                    intencore = False
                                    df = pd.json_normalize(results_sparql['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stritem = row['item.value']
                                            strwikidataid = stritem.split('/')[-1]
                                            strproperty = row['property.value']
                                            # Compute strpropertyid
                                            strpropertyid = ""
                                            strpropertyid = strproperty.split('/')[-1]
                                            stritemid = ""
                                            if 'value.value' in row:
                                                if row['value.value']:
                                                    if not pd.isna(row['value.value']):
                                                        stritemvalue = row['value.value']
                                                        stritemid = stritemvalue.split('/')[-1]
                                            arritemcouples = {}
                                            arritemcouples["ID_WIKIDATA"] = strwikidataid
                                            arritemcouples["ID_PROPERTY"] = strpropertyid
                                            arritemcouples["ID_ITEM"] = stritemid
                                            strsqltablename = "T_WC_WIKIDATA_ITEM_PROPERTY"
                                            strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}' AND ID_PROPERTY = '{strpropertyid}' AND ID_ITEM = '{stritemid}'"
                                            cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                            # Mark every serie in the batch as completed — items with no
                            # properties simply don't appear in the SPARQL result set.
                            for row3 in arrrowsbatch:
                                tf.f_tmdbseriesetwikidatacompleted(row3['ID_SERIE'])

                if intindex == 116:
                    # Wikidata season properties data download
                    cp.f_setservervariable("strsparqlcrawlerseasonpropertiescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT DISTINCT T_WC_TMDB_SEASON.ID_WIKIDATA, T_WC_TMDB_SEASON.TITLE, T_WC_TMDB_SEASON.SEASON_NUMBER, T_WC_TMDB_SEASON.AIR_YEAR, T_WC_TMDB_SEASON.ID_SEASON, T_WC_TMDB_SEASON.ID_SERIE, T_WC_TMDB_SEASON.ID_IMDB, T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating "
                    strsql += "FROM T_WC_TMDB_SEASON "
                    strsql += "LEFT JOIN T_WC_IMDB_MOVIE_RATING_IMPORT ON T_WC_TMDB_SEASON.ID_IMDB = T_WC_IMDB_MOVIE_RATING_IMPORT.tconst "
                    strsql += "WHERE T_WC_TMDB_SEASON.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_SEASON.ID_WIKIDATA <> '' "
                    strsql += "AND T_WC_TMDB_SEASON.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                    strsql += "AND T_WC_TMDB_SEASON.ID_WIKIDATA LIKE 'Q%' "
                    strsql += "AND (T_WC_TMDB_SEASON.TIM_WIKIDATA_COMPLETED IS NULL OR T_WC_TMDB_SEASON.TIM_WIKIDATA_COMPLETED < '" + strdatjminus30 + "') "
                    strsql += "ORDER BY T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating DESC "
                    strsql += "LIMIT 10000 "
                    # strsql += "LIMIT 1 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        # Print per-item context so logs still show what's being processed,
                        # then group ids into batches and issue one POST per batch.
                        for row3 in results:
                            lngid = row3['ID_SEASON']
                            strwikidataid = row3['ID_WIKIDATA']
                            strseasontitle = row3['TITLE']
                            lngseasonnumber = row3['SEASON_NUMBER']
                            stryear = row3['AIR_YEAR']
                            dblimdbrating = row3['averageRating']
                            strmessage = f"{lngid} S{lngseasonnumber} {strseasontitle} ({stryear})"
                            strmessage += f" {dblimdbrating} {strwikidataid}"
                            print(strmessage)
                        # Batch WDQS calls instead of one HTTP round-trip per season:
                        # a single VALUES ?item { wd:Q1 wd:Q2 ... } query returns many items at once,
                        # cuts rate-limit pressure by ~lngbatchsize, and avoids the 1000s 429 back-off loop.
                        # The ?p/?statement/?value claim expansion explodes per item, so keep
                        # the batch small to stay under the WDQS 60s timeout.
                        arrrowsall = list(results)
                        lngbatchsize = 50
                        for lngi in range(0, len(arrrowsall), lngbatchsize):
                            arrrowsbatch = arrrowsall[lngi:lngi + lngbatchsize]
                            arrbatch = [r['ID_WIKIDATA'] for r in arrrowsbatch]
                            strbatchidswd = " ".join([f"wd:{x}" for x in arrbatch])
                            strbatchlabel = f"{arrbatch[0]}..{arrbatch[-1]} ({len(arrbatch)} ids)"
                            cp.f_setservervariable("strsparqlcrawlerseasonpropertiescurrentvalue",strbatchlabel,"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawlerseasonpropertieswikidataid",arrbatch[-1],"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            print(f"batch {lngi // lngbatchsize + 1}: {strbatchlabel}")
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                # Define the SPARQL query
                                strlang = "en"
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?item ?property ?propertyLabel ?value ?valueLabel WHERE { "
                                strsparqlquery += "VALUES ?item { " + strbatchidswd + " } "
                                strsparqlquery += "  ?item ?p ?statement . "
                                strsparqlquery += "  ?statement ?ps ?value . "
                                strsparqlquery += "  ?property wikibase:claim ?p . "
                                strsparqlquery += "  ?property rdfs:label ?propertyLabel FILTER(LANG(?propertyLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "  ?value rdfs:label ?valueLabel FILTER(LANG(?valueLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "} "
                                strsparqlquery += "ORDER BY ?item ?property ?propertyLabel "
                                # Initialize the SPARQL wrapper
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                # Set the query and return format
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                # Execute the query and convert the results
                                try:
                                    query_result = sparql.query()
                                    results_sparql = query_result.convert()
                                    intencore = False
                                    df = pd.json_normalize(results_sparql['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stritem = row['item.value']
                                            strwikidataid = stritem.split('/')[-1]
                                            strproperty = row['property.value']
                                            # Compute strpropertyid
                                            strpropertyid = ""
                                            strpropertyid = strproperty.split('/')[-1]
                                            stritemid = ""
                                            if 'value.value' in row:
                                                if row['value.value']:
                                                    if not pd.isna(row['value.value']):
                                                        stritemvalue = row['value.value']
                                                        stritemid = stritemvalue.split('/')[-1]
                                            arritemcouples = {}
                                            arritemcouples["ID_WIKIDATA"] = strwikidataid
                                            arritemcouples["ID_PROPERTY"] = strpropertyid
                                            arritemcouples["ID_ITEM"] = stritemid
                                            strsqltablename = "T_WC_WIKIDATA_ITEM_PROPERTY"
                                            strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}' AND ID_PROPERTY = '{strpropertyid}' AND ID_ITEM = '{stritemid}'"
                                            cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                            # Mark every season in the batch as completed — items with no
                            # properties simply don't appear in the SPARQL result set.
                            for row3 in arrrowsbatch:
                                tf.f_tmdbseasonsetwikidatacompleted(row3['ID_SEASON'])

                if intindex == 117:
                    # Wikidata episode properties data download
                    cp.f_setservervariable("strsparqlcrawlerepisodepropertiescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT DISTINCT T_WC_TMDB_EPISODE.ID_WIKIDATA, T_WC_TMDB_EPISODE.TITLE, T_WC_TMDB_EPISODE.SEASON_NUMBER, T_WC_TMDB_EPISODE.EPISODE_NUMBER, T_WC_TMDB_EPISODE.AIR_YEAR, T_WC_TMDB_EPISODE.ID_EPISODE, T_WC_TMDB_EPISODE.ID_SERIE, T_WC_TMDB_EPISODE.ID_SEASON, T_WC_TMDB_EPISODE.ID_IMDB, T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating "
                    strsql += "FROM T_WC_TMDB_EPISODE "
                    strsql += "LEFT JOIN T_WC_IMDB_MOVIE_RATING_IMPORT ON T_WC_TMDB_EPISODE.ID_IMDB = T_WC_IMDB_MOVIE_RATING_IMPORT.tconst "
                    strsql += "WHERE T_WC_TMDB_EPISODE.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_EPISODE.ID_WIKIDATA <> '' "
                    strsql += "AND T_WC_TMDB_EPISODE.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                    strsql += "AND T_WC_TMDB_EPISODE.ID_WIKIDATA LIKE 'Q%' "
                    strsql += "AND (T_WC_TMDB_EPISODE.TIM_WIKIDATA_COMPLETED IS NULL OR T_WC_TMDB_EPISODE.TIM_WIKIDATA_COMPLETED < '" + strdatjminus30 + "') "
                    strsql += "ORDER BY T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating DESC "
                    strsql += "LIMIT 20000 "
                    # strsql += "LIMIT 1 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        # Print per-item context so logs still show what's being processed,
                        # then group ids into batches and issue one POST per batch.
                        for row3 in results:
                            lngid = row3['ID_EPISODE']
                            strwikidataid = row3['ID_WIKIDATA']
                            strepisodetitle = row3['TITLE']
                            lngseasonnumber = row3['SEASON_NUMBER']
                            lngepisodenumber = row3['EPISODE_NUMBER']
                            stryear = row3['AIR_YEAR']
                            dblimdbrating = row3['averageRating']
                            strmessage = f"{lngid} S{lngseasonnumber}E{lngepisodenumber} {strepisodetitle} ({stryear})"
                            strmessage += f" {dblimdbrating} {strwikidataid}"
                            print(strmessage)
                        # Batch WDQS calls instead of one HTTP round-trip per episode:
                        # a single VALUES ?item { wd:Q1 wd:Q2 ... } query returns many items at once,
                        # cuts rate-limit pressure by ~lngbatchsize, and avoids the 1000s 429 back-off loop.
                        # The ?p/?statement/?value claim expansion explodes per item, so keep
                        # the batch small to stay under the WDQS 60s timeout.
                        arrrowsall = list(results)
                        lngbatchsize = 50
                        for lngi in range(0, len(arrrowsall), lngbatchsize):
                            arrrowsbatch = arrrowsall[lngi:lngi + lngbatchsize]
                            arrbatch = [r['ID_WIKIDATA'] for r in arrrowsbatch]
                            strbatchidswd = " ".join([f"wd:{x}" for x in arrbatch])
                            strbatchlabel = f"{arrbatch[0]}..{arrbatch[-1]} ({len(arrbatch)} ids)"
                            cp.f_setservervariable("strsparqlcrawlerepisodepropertiescurrentvalue",strbatchlabel,"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawlerepisodepropertieswikidataid",arrbatch[-1],"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            print(f"batch {lngi // lngbatchsize + 1}: {strbatchlabel}")
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                # Define the SPARQL query
                                strlang = "en"
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?item ?property ?propertyLabel ?value ?valueLabel WHERE { "
                                strsparqlquery += "VALUES ?item { " + strbatchidswd + " } "
                                strsparqlquery += "  ?item ?p ?statement . "
                                strsparqlquery += "  ?statement ?ps ?value . "
                                strsparqlquery += "  ?property wikibase:claim ?p . "
                                strsparqlquery += "  ?property rdfs:label ?propertyLabel FILTER(LANG(?propertyLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "  ?value rdfs:label ?valueLabel FILTER(LANG(?valueLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "} "
                                strsparqlquery += "ORDER BY ?item ?property ?propertyLabel "
                                # Initialize the SPARQL wrapper
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                # Set the query and return format
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                # Execute the query and convert the results
                                try:
                                    query_result = sparql.query()
                                    results_sparql = query_result.convert()
                                    intencore = False
                                    df = pd.json_normalize(results_sparql['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stritem = row['item.value']
                                            strwikidataid = stritem.split('/')[-1]
                                            strproperty = row['property.value']
                                            # Compute strpropertyid
                                            strpropertyid = ""
                                            strpropertyid = strproperty.split('/')[-1]
                                            stritemid = ""
                                            if 'value.value' in row:
                                                if row['value.value']:
                                                    if not pd.isna(row['value.value']):
                                                        stritemvalue = row['value.value']
                                                        stritemid = stritemvalue.split('/')[-1]
                                            arritemcouples = {}
                                            arritemcouples["ID_WIKIDATA"] = strwikidataid
                                            arritemcouples["ID_PROPERTY"] = strpropertyid
                                            arritemcouples["ID_ITEM"] = stritemid
                                            strsqltablename = "T_WC_WIKIDATA_ITEM_PROPERTY"
                                            strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}' AND ID_PROPERTY = '{strpropertyid}' AND ID_ITEM = '{stritemid}'"
                                            cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                            # Mark every episode in the batch as completed — items with no
                            # properties simply don't appear in the SPARQL result set.
                            for row3 in arrrowsbatch:
                                tf.f_tmdbepisodesetwikidatacompleted(row3['ID_EPISODE'])

                if intindex == 105 or intindex == 115:
                    # Wikidata person properties data download
                    cp.f_setservervariable("strsparqlcrawlerpersonpropertiescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    if intindex == 115:
                        # Enable the following SQL query to update all persons with VIP status 
                        strsql = f"""SELECT DISTINCT T_WC_TMDB_PERSON.ID_WIKIDATA, T_WC_TMDB_PERSON.NAME, T_WC_TMDB_PERSON.ID_PERSON, T_WC_TMDB_PERSON.POPULARITY 
                        FROM T_WC_TMDB_PERSON 
                        INNER JOIN T_WC_TMDB_PERSON_SEARCH ON T_WC_TMDB_PERSON.ID_PERSON = T_WC_TMDB_PERSON_SEARCH.ID_PERSON 
WHERE T_WC_TMDB_PERSON.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_PERSON.ID_WIKIDATA <> '' 
AND T_WC_TMDB_PERSON.ID_WIKIDATA REGEXP '^Q[0-9]+$'
AND T_WC_TMDB_PERSON.ID_WIKIDATA LIKE 'Q%' 
AND (T_WC_TMDB_PERSON.TIM_WIKIDATA_COMPLETED IS NULL OR T_WC_TMDB_PERSON.TIM_WIKIDATA_COMPLETED < '{strdatjminus100}') 
ORDER BY T_WC_TMDB_PERSON.ID_PERSON ASC 
"""
                    else:
                        # Regular update of persons
                        strsql = ""
                        strsql += "SELECT DISTINCT T_WC_TMDB_PERSON.ID_WIKIDATA, T_WC_TMDB_PERSON.NAME, T_WC_TMDB_PERSON.ID_PERSON, T_WC_TMDB_PERSON.POPULARITY "
                        strsql += "FROM T_WC_TMDB_PERSON "
                        #strsql += "INNER JOIN T_WC_WIKIDATA_PERSON_V1 ON T_WC_TMDB_PERSON.ID_WIKIDATA = T_WC_WIKIDATA_PERSON_V1.ID_WIKIDATA "
                        strsql += "WHERE T_WC_TMDB_PERSON.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_PERSON.ID_WIKIDATA <> '' "
                        strsql += "AND T_WC_TMDB_PERSON.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                        strsql += "AND T_WC_TMDB_PERSON.ID_WIKIDATA LIKE 'Q%' "
                        strsql += "AND (T_WC_TMDB_PERSON.TIM_WIKIDATA_COMPLETED IS NULL OR T_WC_TMDB_PERSON.TIM_WIKIDATA_COMPLETED < '" + strdatjminus30 + "') "
                        strsql += "ORDER BY T_WC_TMDB_PERSON.POPULARITY DESC "
                        strsql += "LIMIT 20000 "
                        # strsql += "LIMIT 1 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        # Print per-item context so logs still show what's being processed,
                        # then group ids into 500-id batches and issue one POST per batch.
                        for row3 in results:
                            lngid = row3['ID_PERSON']
                            strwikidataid = row3['ID_WIKIDATA']
                            strpersonname = row3['NAME']
                            dblpersonpopularity = row3['POPULARITY']
                            strmessage = f"{lngid} {strpersonname}"
                            strmessage += f" {dblpersonpopularity} {strwikidataid}"
                            print(strmessage)
                        # Batch WDQS calls instead of one HTTP round-trip per person:
                        # a single VALUES ?item { wd:Q1 wd:Q2 ... } query returns many items at once,
                        # cuts rate-limit pressure by ~lngbatchsize, and avoids the 1000s 429 back-off loop.
                        # Persons carry the most claims of any item type (occupations, awards,
                        # citizenships, dates), so keep the batch tighter than movies/series.
                        arrrowsall = list(results)
                        lngbatchsize = 25
                        for lngi in range(0, len(arrrowsall), lngbatchsize):
                            arrrowsbatch = arrrowsall[lngi:lngi + lngbatchsize]
                            arrbatch = [r['ID_WIKIDATA'] for r in arrrowsbatch]
                            strbatchidswd = " ".join([f"wd:{x}" for x in arrbatch])
                            strbatchlabel = f"{arrbatch[0]}..{arrbatch[-1]} ({len(arrbatch)} ids)"
                            cp.f_setservervariable("strsparqlcrawlerpersonspropertiescurrentvalue",strbatchlabel,"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawlerpersonspropertieswikidataid",arrbatch[-1],"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            print(f"batch {lngi // lngbatchsize + 1}: {strbatchlabel}")
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                # Define the SPARQL query
                                strlang = "en"
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?item ?property ?propertyLabel ?value ?valueLabel WHERE { "
                                strsparqlquery += "VALUES ?item { " + strbatchidswd + " } "
                                strsparqlquery += "  ?item ?p ?statement . "
                                strsparqlquery += "  ?statement ?ps ?value . "
                                strsparqlquery += "  ?property wikibase:claim ?p . "
                                strsparqlquery += "  ?property rdfs:label ?propertyLabel FILTER(LANG(?propertyLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "  ?value rdfs:label ?valueLabel FILTER(LANG(?valueLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "} "
                                strsparqlquery += "ORDER BY ?item ?property ?propertyLabel "
                                # Initialize the SPARQL wrapper
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                # Set the query and return format
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                # Execute the query and convert the results
                                try:
                                    query_result = sparql.query()
                                    results_sparql = query_result.convert()
                                    intencore = False
                                    df = pd.json_normalize(results_sparql['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stritem = row['item.value']
                                            strwikidataid = stritem.split('/')[-1]
                                            strproperty = row['property.value']
                                            # Compute strpropertyid
                                            strpropertyid = ""
                                            strpropertyid = strproperty.split('/')[-1]
                                            stritemid = ""
                                            if 'value.value' in row:
                                                if row['value.value']:
                                                    if not pd.isna(row['value.value']):
                                                        stritemvalue = row['value.value']
                                                        stritemid = stritemvalue.split('/')[-1]
                                            arritemcouples = {}
                                            arritemcouples["ID_WIKIDATA"] = strwikidataid
                                            arritemcouples["ID_PROPERTY"] = strpropertyid
                                            arritemcouples["ID_ITEM"] = stritemid
                                            strsqltablename = "T_WC_WIKIDATA_ITEM_PROPERTY"
                                            strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}' AND ID_PROPERTY = '{strpropertyid}' AND ID_ITEM = '{stritemid}'"
                                            cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                            # Mark every person in the batch as completed — items with no
                            # properties simply don't appear in the SPARQL result set.
                            for row3 in arrrowsbatch:
                                tf.f_tmdbpersonsetwikidatacompleted(row3['ID_PERSON'])
                if intindex in (118, 119, 120, 121, 122, 123, 124, 125, 126, 127):
                    # Wikidata T2S entity properties data download.
                    # Same flow as scope 116 (season properties): per-batch VALUES ?item SPARQL
                    # query, upsert into T_WC_WIKIDATA_ITEM_PROPERTY, then mark each parent's
                    # TIM_WIKIDATA_COMPLETED. T2S tables are preferred over their TMDb
                    # counterparts because the text2sql data-prep pipeline reliably populates
                    # ID_WIKIDATA on the T2S side (see AGENTS.md scope-discovery rules).
                    # The 10 scopes are parameterized via arrt2sscope rather than copy-pasted
                    # 90-line blocks so changes to the SPARQL pattern stay in one place.
                    arrt2sscope = {
                        118: {'table': 'T_WC_T2S_COLLECTION', 'pk': 'ID_T2S_COLLECTION', 'label': 'COLLECTION_NAME', 'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2scollectionsetwikidatacompleted, 'svvar': 'collection'},
                        119: {'table': 'T_WC_T2S_CHARACTER',  'pk': 'ID_CHARACTER',      'label': 'CAST_CHARACTER',  'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2scharactersetwikidatacompleted,  'svvar': 'character'},
                        120: {'table': 'T_WC_T2S_AWARD',      'pk': 'ID_AWARD',          'label': 'AWARD_NAME',      'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2sawardsetwikidatacompleted,      'svvar': 'award'},
                        121: {'table': 'T_WC_T2S_NOMINATION', 'pk': 'ID_NOMINATION',     'label': 'NOMINATION_NAME', 'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2snominationsetwikidatacompleted, 'svvar': 'nomination'},
                        122: {'table': 'T_WC_T2S_TOPIC',      'pk': 'ID_TOPIC',          'label': 'TOPIC_NAME',      'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2stopicsetwikidatacompleted,      'svvar': 'topic'},
                        123: {'table': 'T_WC_T2S_TECHNICAL',  'pk': 'ID_TECHNICAL',      'label': 'DESCRIPTION',     'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2stechnicalsetwikidatacompleted,  'svvar': 'technical'},
                        124: {'table': 'T_WC_T2S_GROUP',      'pk': 'ID_GROUP',          'label': 'GROUP_NAME',      'order': 'POPULARITY',           'helper': tf.f_t2sgroupsetwikidatacompleted,      'svvar': 'group'},
                        125: {'table': 'T_WC_T2S_MOVEMENT',   'pk': 'ID_MOVEMENT',       'label': 'MOVEMENT_NAME',   'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2smovementsetwikidatacompleted,   'svvar': 'movement'},
                        126: {'table': 'T_WC_T2S_LIST',       'pk': 'ID_T2S_LIST',       'label': 'LIST_NAME',       'order': 'IMDB_RATING_WEIGHTED', 'helper': tf.f_t2slistsetwikidatacompleted,       'svvar': 'list'},
                        127: {'table': 'T_WC_T2S_DEATH',      'pk': 'ID_DEATH',          'label': 'DEATH_NAME',      'order': 'POPULARITY',           'helper': tf.f_t2sdeathsetwikidatacompleted,      'svvar': 'death'},
                    }
                    cfg = arrt2sscope[intindex]
                    strsvbase = f"strsparqlcrawlert2s{cfg['svvar']}properties"
                    cp.f_setservervariable(f"{strsvbase}currentprocess", strcurrentprocess, "Current process in the Wikidata SPARQL crawler", 0)
                    # Backtick the table name because T_WC_T2S_GROUP collides with the MySQL
                    # reserved word GROUP; uniform backticking keeps the SQL identical across scopes.
                    strsql = ""
                    strsql += f"SELECT DISTINCT `{cfg['table']}`.{cfg['pk']} AS PK, `{cfg['table']}`.ID_WIKIDATA, `{cfg['table']}`.{cfg['label']} AS LABEL "
                    strsql += f"FROM `{cfg['table']}` "
                    strsql += f"WHERE `{cfg['table']}`.ID_WIKIDATA IS NOT NULL AND `{cfg['table']}`.ID_WIKIDATA <> '' "
                    strsql += f"AND `{cfg['table']}`.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                    strsql += f"AND `{cfg['table']}`.ID_WIKIDATA LIKE 'Q%' "
                    strsql += f"AND (`{cfg['table']}`.TIM_WIKIDATA_COMPLETED IS NULL OR `{cfg['table']}`.TIM_WIKIDATA_COMPLETED < '" + strdatjminus30 + "') "
                    strsql += f"ORDER BY `{cfg['table']}`.{cfg['order']} DESC "
                    strsql += "LIMIT 10000 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        for row3 in results:
                            print(f"{row3['PK']} {row3['LABEL']} {row3['ID_WIKIDATA']}")
                        # Batch WDQS calls instead of one HTTP round-trip per item: a single
                        # VALUES ?item { wd:Q1 wd:Q2 ... } query returns many items at once.
                        arrrowsall = list(results)
                        lngbatchsize = 50
                        for lngi in range(0, len(arrrowsall), lngbatchsize):
                            arrrowsbatch = arrrowsall[lngi:lngi + lngbatchsize]
                            arrbatch = [r['ID_WIKIDATA'] for r in arrrowsbatch]
                            strbatchidswd = " ".join([f"wd:{x}" for x in arrbatch])
                            strbatchlabel = f"{arrbatch[0]}..{arrbatch[-1]} ({len(arrbatch)} ids)"
                            cp.f_setservervariable(f"{strsvbase}currentvalue", strbatchlabel, "Current value in the current Wikidata SPARQL crawler", 0)
                            cp.f_setservervariable(f"{strsvbase}wikidataid", arrbatch[-1], "Current Wikidata ID in the current Wikidata SPARQL crawler", 0)
                            print(f"batch {lngi // lngbatchsize + 1}: {strbatchlabel}")
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                strlang = "en"
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?item ?property ?propertyLabel ?value ?valueLabel WHERE { "
                                strsparqlquery += "VALUES ?item { " + strbatchidswd + " } "
                                strsparqlquery += "  ?item ?p ?statement . "
                                strsparqlquery += "  ?statement ?ps ?value . "
                                strsparqlquery += "  ?property wikibase:claim ?p . "
                                strsparqlquery += "  ?property rdfs:label ?propertyLabel FILTER(LANG(?propertyLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "  ?value rdfs:label ?valueLabel FILTER(LANG(?valueLabel) = \"" + strlang + "\") . "
                                strsparqlquery += "} "
                                strsparqlquery += "ORDER BY ?item ?property ?propertyLabel "
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                try:
                                    query_result = sparql.query()
                                    results_sparql = query_result.convert()
                                    intencore = False
                                    df = pd.json_normalize(results_sparql['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stritem = row['item.value']
                                            strwikidataid = stritem.split('/')[-1]
                                            strproperty = row['property.value']
                                            strpropertyid = strproperty.split('/')[-1]
                                            stritemid = ""
                                            if 'value.value' in row:
                                                if row['value.value']:
                                                    if not pd.isna(row['value.value']):
                                                        stritemvalue = row['value.value']
                                                        stritemid = stritemvalue.split('/')[-1]
                                            arritemcouples = {}
                                            arritemcouples["ID_WIKIDATA"] = strwikidataid
                                            arritemcouples["ID_PROPERTY"] = strpropertyid
                                            arritemcouples["ID_ITEM"] = stritemid
                                            strsqltablename = "T_WC_WIKIDATA_ITEM_PROPERTY"
                                            strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}' AND ID_PROPERTY = '{strpropertyid}' AND ID_ITEM = '{stritemid}'"
                                            cp.f_sqlupdatearray(strsqltablename, arritemcouples, strsqlupdatecondition, 1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                            # Mark every row in the batch as completed — items with no
                            # properties simply don't appear in the SPARQL result set.
                            for row3 in arrrowsbatch:
                                cfg['helper'](row3['PK'])
                if intindex == 106:
                    # Wikidata movie aliases data download
                    cp.f_setservervariable("strsparqlcrawlermoviealiasescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT DISTINCT T_WC_TMDB_MOVIE.ID_WIKIDATA, T_WC_TMDB_MOVIE.TITLE, T_WC_TMDB_MOVIE.ORIGINAL_TITLE, T_WC_TMDB_MOVIE.DAT_RELEASE, T_WC_TMDB_MOVIE.ID_MOVIE, T_WC_TMDB_MOVIE.ID_IMDB, T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating "
                    strsql += "FROM T_WC_TMDB_MOVIE "
                    strsql += "INNER JOIN T_WC_WIKIDATA_MOVIE_V1 ON T_WC_TMDB_MOVIE.ID_WIKIDATA = T_WC_WIKIDATA_MOVIE_V1.ID_WIKIDATA "
                    strsql += "LEFT JOIN T_WC_IMDB_MOVIE_RATING_IMPORT ON T_WC_TMDB_MOVIE.ID_IMDB = T_WC_IMDB_MOVIE_RATING_IMPORT.tconst "
                    strsql += "WHERE T_WC_TMDB_MOVIE.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_MOVIE.ID_WIKIDATA <> '' "
                    strsql += "AND T_WC_TMDB_MOVIE.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                    strsql += "AND T_WC_TMDB_MOVIE.ID_WIKIDATA LIKE 'Q%' "
                    strsql += "AND T_WC_WIKIDATA_MOVIE_V1.ALIASES IS NULL "
                    #strsql += "AND (T_WC_TMDB_MOVIE.ID_MOVIE IN ( "
                    #strsql += "SELECT ID_MOVIE FROM T_WC_TMDB_MOVIE_LIST WHERE ID_LIST IN ( "
                    #strsql += "SELECT ID_LIST FROM T_WC_TMDB_LIST WHERE DELETED = 0 AND USE_FOR_TAGGING >= 1 "
                    #strsql += ") "
                    #strsql += ") "
                    #strsql += "OR (T_WC_WIKIDATA_MOVIE_V1.ID_CRITERION IS NOT NULL AND T_WC_WIKIDATA_MOVIE_V1.ID_CRITERION <> 0) "
                    #strsql += ") "
                    strsql += "ORDER BY T_WC_IMDB_MOVIE_RATING_IMPORT.averageRating DESC "
                    strsql += "LIMIT 500 "
                    #strsql += "LIMIT 5 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        for row3 in results:
                            # print("------------------------------------------")
                            strwikidataid = row3['ID_WIKIDATA']
                            lngid = row3['ID_MOVIE']
                            strmovietitle = row3['TITLE']
                            strmovieoriginaltitle = row3['ORIGINAL_TITLE']
                            datrelease = row3['DAT_RELEASE']
                            stryearrelease = ""
                            if datrelease:
                                stryearrelease = datrelease.strftime("%Y")
                            dblimdbrating = row3['averageRating']
                            cp.f_setservervariable("strsparqlcrawlermoviealiasescurrentvalue",str(dblimdbrating),"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawlermoviealiaseswikidataid",strwikidataid,"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            strmessage = f"{lngid} {strmovietitle} ({stryearrelease})"
                            if strmovietitle != strmovieoriginaltitle:
                                strmessage += f" AKA {strmovieoriginaltitle}"
                            strmessage += f" {dblimdbrating} {strwikidataid}"
                            print(strmessage)
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                # Define the SPARQL query
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?alias WHERE { "
                                strsparqlquery += "  wd:" + strwikidataid + " skos:altLabel ?alias. "
                                strsparqlquery += "  FILTER(LANG(?alias) IN (\"en\", \"fr\")) "
                                strsparqlquery += "} "
                                # Initialize the SPARQL wrapper
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                # Set the query and return format
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                # Execute the query and convert the results
                                try:
                                    query_result = sparql.query()
                                    results = query_result.convert()
                                    intencore = False
                                    strmoviealiases = "|"
                                    df = pd.json_normalize(results['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stralias = row['alias.value']
                                            if stralias != "":
                                                straliassearch = "|" + stralias + "|"
                                                if straliassearch not in strmoviealiases:
                                                    strmoviealiases += stralias + "|"
                                    arritemcouples = {}
                                    arritemcouples["ID_WIKIDATA"] = strwikidataid
                                    arritemcouples["ALIASES"] = strmoviealiases
                                    strsqltablename = "T_WC_WIKIDATA_MOVIE_V1"
                                    strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}'"
                                    cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                if intindex == 107:
                    # Wikidata person aliases data download
                    cp.f_setservervariable("strsparqlcrawlerpersonaliasescurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT DISTINCT T_WC_TMDB_PERSON.ID_WIKIDATA, T_WC_TMDB_PERSON.NAME, T_WC_TMDB_PERSON.ID_PERSON, T_WC_TMDB_PERSON.POPULARITY "
                    strsql += "FROM T_WC_TMDB_PERSON "
                    strsql += "INNER JOIN T_WC_WIKIDATA_PERSON_V1 ON T_WC_TMDB_PERSON.ID_WIKIDATA = T_WC_WIKIDATA_PERSON_V1.ID_WIKIDATA "
                    strsql += "WHERE T_WC_TMDB_PERSON.ID_WIKIDATA IS NOT NULL AND T_WC_TMDB_PERSON.ID_WIKIDATA <> '' "
                    strsql += "AND T_WC_TMDB_PERSON.ID_WIKIDATA REGEXP '^Q[0-9]+$' "
                    strsql += "AND T_WC_TMDB_PERSON.ID_WIKIDATA LIKE 'Q%' "
                    strsql += "AND T_WC_WIKIDATA_PERSON_V1.ALIASES IS NULL "
                    #strsql += "AND T_WC_TMDB_PERSON.ID_PERSON = 3829 "
                    strsql += "ORDER BY T_WC_TMDB_PERSON.POPULARITY DESC "
                    strsql += "LIMIT 10000 "
                    #strsql += "LIMIT 5 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        for row3 in results:
                            # print("------------------------------------------")
                            strwikidataid = row3['ID_WIKIDATA']
                            lngid = row3['ID_PERSON']
                            strpersonname = row3['NAME']
                            dblpersonpopularity = row3['POPULARITY']
                            cp.f_setservervariable("strsparqlcrawlerpersonaliasescurrentvalue",str(dblpersonpopularity),"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawlerpersonaliaseswikidataid",strwikidataid,"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            strmessage = f"{lngid} {strpersonname}"
                            strmessage += f" {strwikidataid}"
                            print(strmessage)
                            intencore = True
                            while intencore:
                                time.sleep(5)
                                # Define the SPARQL query
                                strsparqlquery = ""
                                strsparqlquery += "SELECT ?alias WHERE { "
                                strsparqlquery += "  wd:" + strwikidataid + " skos:altLabel ?alias. "
                                strsparqlquery += "  FILTER(LANG(?alias) IN (\"en\", \"fr\")) "
                                strsparqlquery += "} "
                                # Initialize the SPARQL wrapper
                                sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                # Set the query and return format
                                print(strsparqlquery)
                                sparql.setQuery(strsparqlquery)
                                sparql.setReturnFormat(JSON)
                                sparql.setMethod(POST)
                                # Execute the query and convert the results
                                try:
                                    query_result = sparql.query()
                                    results = query_result.convert()
                                    intencore = False
                                    strpersonaliases = "|"
                                    df = pd.json_normalize(results['results']['bindings'])
                                    if not df.empty:
                                        for index, row in df.iterrows():
                                            stralias = row['alias.value']
                                            if stralias != "":
                                                straliassearch = "|" + stralias + "|"
                                                if straliassearch not in strpersonaliases:
                                                    strpersonaliases += stralias + "|"
                                    arritemcouples = {}
                                    arritemcouples["ID_WIKIDATA"] = strwikidataid
                                    arritemcouples["ALIASES"] = strpersonaliases
                                    strsqltablename = "T_WC_WIKIDATA_PERSON_V1"
                                    strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}'"
                                    cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                except SPARQLExceptions.EndPointInternalError as e:
                                    print(f"Internal Server Error: {e}")
                                except SPARQLExceptions.QueryBadFormed as e:
                                    print(f"Badly Formed Query: {e}")
                                except SPARQLExceptions.EndPointNotFound as e:
                                    print(f"Endpoint Not Found: {e}")
                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                    lngretryafter = 60
                                    print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                    time.sleep(lngretryafter)
                if intindex == 109:
                    # Wikidata items data download, new (109)
                    cp.f_setservervariable("strsparqlcrawleritemscurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strwikidataidold = cp.f_getservervariable("strsparqlcrawleritemswikidataid",0)
                    rows_to_process = 5000
                    strsql = ""
                    strsql += "SELECT DISTINCT ID_ITEM "
                    strsql += "FROM T_WC_WIKIDATA_ITEM_PROPERTY "
                    strsql += "WHERE ID_ITEM LIKE 'Q%' "
                    if strwikidataidold != "":
                        strsql += f"AND ID_ITEM > '{strwikidataidold}' "
                    strsql += "AND ID_ITEM NOT IN (SELECT ID_WIKIDATA FROM T_WC_WIKIDATA_ITEM_V1 WHERE LABEL <> '' AND LABEL IS NOT NULL) "
                    strsql += "AND ID_ITEM NOT IN (SELECT ID_WIKIDATA FROM T_WC_WIKIDATA_PERSON_V1 WHERE NAME <> '' AND NAME IS NOT NULL) "
                    strsql += "AND ID_ITEM NOT IN (SELECT ID_WIKIDATA FROM T_WC_WIKIDATA_MOVIE_V1 WHERE TITLE <> '' AND TITLE IS NOT NULL) "
                    strsql += "AND ID_ITEM NOT IN (SELECT ID_WIKIDATA FROM T_WC_WIKIDATA_SERIE_V1 WHERE TITLE <> '' AND TITLE IS NOT NULL) "
                    strsql += "ORDER BY ID_ITEM "
                    strsql += f"LIMIT {rows_to_process} "
                    # strsql += "LIMIT 1 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        # Batch WDQS calls instead of one HTTP round-trip per id:
                        # a single VALUES ?item { wd:Q1 wd:Q2 ... } query returns many items at once,
                        # cuts rate-limit pressure by ~lngbatchsize, and avoids the 1000s 429 back-off loop.
                        arritemidsall = [row3['ID_ITEM'] for row3 in results]
                        # Outer slice (lngbatchsize) is kept at 500 so the cursor variable
                        # strsparqlcrawleritemswikidataid advances in 500-id chunks (matches
                        # rows_to_process accounting and resume semantics). The actual SPARQL
                        # POST is sub-batched per language: the EN pass cycles ~50 fallback
                        # languages in the wikibase:label service so it has to stay smaller;
                        # FR only walks ~10 fallback languages and can absorb the full slice.
                        lngbatchsize = 500
                        arrlangbatchsize = {1: 200, 2: 500}
                        for lngi in range(0, len(arritemidsall), lngbatchsize):
                            arrouterbatch = arritemidsall[lngi:lngi + lngbatchsize]
                            strbatchlabel = f"{arrouterbatch[0]}..{arrouterbatch[-1]} ({len(arrouterbatch)} ids)"
                            cp.f_setservervariable("strsparqlcrawleritemscurrentvalue",strbatchlabel,"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawleritemswikidataid",arrouterbatch[-1],"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            print(f"batch {lngi // lngbatchsize + 1}: {strbatchlabel}")
                            arrlang = {1: 'en', 2: 'fr'}
                            for intlang, strlang in arrlang.items():
                                if strlang == "en":
                                    strlangfull = "en,de,es,it,pt,ru,zh,ja,fr,nl,sv,pl,fi,cs,hu,da,ro,ko,ar,he,el,vi,th,uk,ca,eo,gl,la,li,lt,ms,nn,oc,or,ps,qu,sa,sc,sr,sw,tg,tk,tl,tt,ug,ve,wuu,xh,yor,zul"
                                elif strlang == "fr":
                                    strlangfull = "fr,en,de,es,it,pt,ru,zh,ja"
                                lngsubbatchsize = arrlangbatchsize[intlang]
                                for lngj in range(0, len(arrouterbatch), lngsubbatchsize):
                                    arrbatch = arrouterbatch[lngj:lngj + lngsubbatchsize]
                                    strbatchidswd = " ".join([f"wd:{x}" for x in arrbatch])
                                    print(f"  {strlang} sub-batch {lngj // lngsubbatchsize + 1}: {arrbatch[0]}..{arrbatch[-1]} ({len(arrbatch)} ids)")
                                    intencore = True
                                    while intencore:
                                        time.sleep(5)
                                        # Define the SPARQL query
                                        strsparqlquery = ""
                                        strsparqlquery += "SELECT ?item ?itemLabel ?itemDescription ?itemAlias ?instanceOf WHERE { "
                                        strsparqlquery += "VALUES ?item { " + strbatchidswd + " } "
                                        strsparqlquery += "OPTIONAL { ?item wdt:P31 ?instanceOf } "
                                        strsparqlquery += "SERVICE wikibase:label {  "
                                        strsparqlquery += "bd:serviceParam wikibase:language \"" + strlangfull + "\". "
                                        strsparqlquery += "} "
                                        strsparqlquery += "OPTIONAL { ?item skos:altLabel ?itemAlias. FILTER (LANG(?itemAlias) = \"" + strlang + "\") } "
                                        strsparqlquery += "} "
                                        # ORDER BY ?item keeps rows for the same item adjacent so the prev-id stream works
                                        strsparqlquery += "ORDER BY ?item "
                                        # Initialize the SPARQL wrapper
                                        sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                        # Set the query and return format
                                        print(strsparqlquery)
                                        sparql.setQuery(strsparqlquery)
                                        sparql.setReturnFormat(JSON)
                                        sparql.setMethod(POST)
                                        # Execute the query and convert the results
                                        try:
                                            query_result = sparql.query()
                                            results = query_result.convert()
                                            intencore = False
                                            df = pd.json_normalize(results['results']['bindings'])
                                            if not df.empty:
                                                # Stream rows grouped by ?item: flush each accumulated item
                                                # on transition, then flush the last one after the loop
                                                strwikidataidprev = ""
                                                strlabel = ""
                                                strdescription = ""
                                                straliases = ""
                                                strinstanceof = ""
                                                strinstanceofid = ""
                                                for index, row in df.iterrows():
                                                    stritem = row['item.value']
                                                    strwikidataidcur = stritem.split('/')[-1]
                                                    if strwikidataidcur != strwikidataidprev:
                                                        if strwikidataidprev != "":
                                                            arritemcouples = {}
                                                            arritemcouples["ID_WIKIDATA"] = strwikidataidprev
                                                            arritemcouples["LANG"] = strlang
                                                            arritemcouples["LABEL"] = strlabel
                                                            arritemcouples["DESCRIPTION"] = strdescription
                                                            arritemcouples["ALIASES"] = straliases
                                                            arritemcouples["INSTANCE_OF"] = strinstanceofid
                                                            strsqltablename = "T_WC_WIKIDATA_ITEM_V1"
                                                            strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataidprev}' AND LANG = '{strlang}'"
                                                            cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                                        strwikidataidprev = strwikidataidcur
                                                        strlabel = ""
                                                        strdescription = ""
                                                        straliases = ""
                                                        strinstanceof = ""
                                                        strinstanceofid = ""
                                                    if strlabel == "":
                                                        if 'itemLabel.value' in row:
                                                            if row['itemLabel.value']:
                                                                if not pd.isna(row['itemLabel.value']):
                                                                    strlabel = row['itemLabel.value']
                                                                    # reject any label that looks like a Wikidata ID
                                                                    if re.match(r'^[QPL]\d+$', strlabel):
                                                                        strlabel = ""
                                                    if strdescription == "":
                                                        if 'itemDescription.value' in row:
                                                            if row['itemDescription.value']:
                                                                if not pd.isna(row['itemDescription.value']):
                                                                    strdescription = row['itemDescription.value']
                                                    if 'itemAlias.value' in row:
                                                        if row['itemAlias.value']:
                                                            if not pd.isna(row['itemAlias.value']):
                                                                stralias = row['itemAlias.value']
                                                                if stralias != "":
                                                                    if straliases == "":
                                                                        straliases = "|"
                                                                    straliases += stralias + "|"
                                                    if 'instanceOf.value' in row:
                                                        if row['instanceOf.value']:
                                                            if not pd.isna(row['instanceOf.value']):
                                                                strinstanceof = row['instanceOf.value']
                                                                strinstanceofid = strinstanceof.split('/')[-1]
                                                # End of the loop for the current batch so we flush the last item
                                                if strwikidataidprev != "":
                                                    arritemcouples = {}
                                                    arritemcouples["ID_WIKIDATA"] = strwikidataidprev
                                                    arritemcouples["LANG"] = strlang
                                                    arritemcouples["LABEL"] = strlabel
                                                    arritemcouples["DESCRIPTION"] = strdescription
                                                    arritemcouples["ALIASES"] = straliases
                                                    arritemcouples["INSTANCE_OF"] = strinstanceofid
                                                    strsqltablename = "T_WC_WIKIDATA_ITEM_V1"
                                                    strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataidprev}' AND LANG = '{strlang}'"
                                                    cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                        except SPARQLExceptions.EndPointInternalError as e:
                                            print(f"Internal Server Error: {e}")
                                        except SPARQLExceptions.QueryBadFormed as e:
                                            print(f"Badly Formed Query: {e}")
                                        except SPARQLExceptions.EndPointNotFound as e:
                                            print(f"Endpoint Not Found: {e}")
                                        except Exception as e:
                                            print(f"An error occurred: {e}")
                                            lngretryafter = 60
                                            print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                            time.sleep(lngretryafter)
                        if lngrowcount < rows_to_process:
                            # We finished crawling all items, we can reset the last Wikidata ID to process
                            cp.f_setservervariable("strsparqlcrawleritemswikidataid","", "Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                if intindex == 110:
                    # Wikidata items data download, fix INSTANCE_OF (110)
                    cp.f_setservervariable("strsparqlcrawleritemscurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT DISTINCT ID_WIKIDATA FROM T_WC_WIKIDATA_ITEM_V1 "
                    strsql += "WHERE INSTANCE_OF IS NULL "
                    strsql += "ORDER BY TIM_UPDATED ASC "
                    #strsql += "LIMIT 100 "
                    # strsql += "LIMIT 1 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        strwikidataidall = ""
                        lngitemcount = 0
                        for row3 in results:
                            strwikidataid = row3['ID_WIKIDATA']
                            strwikidataidall += " wd:" + strwikidataid
                            lngitemcount += 1
                            if lngitemcount >= 500:
                                print(strwikidataidall)
                                intencore = True
                                while intencore:
                                    time.sleep(5)
                                    # Define the SPARQL query
                                    strsparqlquery = ""
                                    strsparqlquery += "SELECT ?item ?instanceOf WHERE { "
                                    strsparqlquery += "VALUES ?item { " + strwikidataidall + " } "
                                    strsparqlquery += "?item wdt:P31 ?instanceOf. "
                                    strsparqlquery += "} "
                                    # Initialize the SPARQL wrapper
                                    sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent=strwikidatauseragent)
                                    # Set the query and return format
                                    print(strsparqlquery)
                                    sparql.setQuery(strsparqlquery)
                                    sparql.setReturnFormat(JSON)
                                    sparql.setMethod(POST)
                                    # Execute the query and convert the results
                                    try:
                                        query_result = sparql.query()
                                        results = query_result.convert()
                                        intencore = False
                                        df = pd.json_normalize(results['results']['bindings'])
                                        if not df.empty:
                                            for index, row in df.iterrows():
                                                stritem = row['item.value']
                                                # Compute strwikidataid
                                                strwikidataid = ""
                                                strwikidataid = stritem.split('/')[-1]
                                                cp.f_setservervariable("strsparqlcrawleritemfixinstanceofcurrentvalue",strwikidataid,"Current value in the current Wikidata SPARQL crawler",0)
                                                cp.f_setservervariable("strsparqlcrawleritemfixinstanceofwikidataid",strwikidataid,"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                                                strinstanceof = ""
                                                strinstanceofid = ""
                                                if 'instanceOf.value' in row:
                                                    if row['instanceOf.value']:
                                                        if not pd.isna(row['instanceOf.value']):
                                                            strinstanceof = row['instanceOf.value']
                                                            strinstanceofid = strinstanceof.split('/')[-1]
                                                arritemcouples = {}
                                                arritemcouples["ID_WIKIDATA"] = strwikidataid
                                                arritemcouples["INSTANCE_OF"] = strinstanceofid
                                                strsqltablename = "T_WC_WIKIDATA_ITEM_V1"
                                                strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}' "
                                                cp.f_sqlupdatearray(strsqltablename,arritemcouples,strsqlupdatecondition,1)
                                                strwikidataidall = ""
                                                lngitemcount = 0
                                    except SPARQLExceptions.EndPointInternalError as e:
                                        print(f"Internal Server Error: {e}")
                                    except SPARQLExceptions.QueryBadFormed as e:
                                        print(f"Badly Formed Query: {e}")
                                    except SPARQLExceptions.EndPointNotFound as e:
                                        print(f"Endpoint Not Found: {e}")
                                    except Exception as e:
                                        print(f"An error occurred: {e}")
                                        lngretryafter = 60
                                        print(f"Rate limit exceeded. Retrying after {lngretryafter} seconds.")
                                        time.sleep(lngretryafter)
                if intindex == 112:
                    # Wikidata move items to person when INSTANCE_OF is Q5
                    cp.f_setservervariable("strsparqlcrawleritemscurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT * FROM T_WC_WIKIDATA_ITEM_V1 "
                    arrinstanceof = [v for v in strsparqlpersoninstanceof.split() if v]
                    if not arrinstanceof:
                        arrinstanceof = ["Q5"]
                    strsqlinstanceof = ",".join([f"'{v}'" for v in arrinstanceof])
                    strsql += f"WHERE INSTANCE_OF IN ({strsqlinstanceof}) "
                    strsql += "AND LANG = 'en' "
                    #strsql += "AND ID_WIKIDATA NOT IN (SELECT ID_WIKIDATA FROM T_WC_WIKIDATA_PERSON_V1) "
                    strsql += "ORDER BY TIM_UPDATED ASC "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        results = cursor.fetchall()
                        for row3 in results:
                            strwikidataid = row3['ID_WIKIDATA']
                            strname = row3['LABEL']
                            straliases = row3['ALIASES']
                            strinstanceofid = row3['INSTANCE_OF']
                            strimagepath = row3['WIKIPEDIA_IMAGE_PATH']
                            cp.f_setservervariable("strsparqlcrawleritemfixinstanceofcurrentvalue",strwikidataid,"Current value in the current Wikidata SPARQL crawler",0)
                            cp.f_setservervariable("strsparqlcrawleritemfixinstanceofwikidataid",strwikidataid,"Current Wikidata ID in the current Wikidata SPARQL crawler",0)
                            strsqlperson = "SELECT * FROM T_WC_WIKIDATA_PERSON_V1 WHERE ID_WIKIDATA = '" + strwikidataid + "' "
                            cursor3.execute(strsqlperson)
                            lngrowcountperson = cursor3.rowcount
                            if lngrowcountperson == 0:
                                # Person does not exist in T_WC_WIKIDATA_PERSON_V1, we can move it
                                print(f"Moving {strwikidataid} {strname} to person")
                                arrpersoncouples = {}
                                arrpersoncouples["ID_WIKIDATA"] = strwikidataid
                                arrpersoncouples["NAME"] = strname
                                arrpersoncouples["ALIASES"] = straliases
                                arrpersoncouples["INSTANCE_OF"] = strinstanceofid
                                arrpersoncouples["WIKIPEDIA_PROFILE_PATH"] = strimagepath
                                strsqltablename = "T_WC_WIKIDATA_PERSON_V1"
                                strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}'"
                                cp.f_sqlupdatearray(strsqltablename,arrpersoncouples,strsqlupdatecondition,1)
                            else:
                                # Person already exists in T_WC_WIKIDATA_PERSON_V1, so we move only non empty values 
                                print(f"Updating {strwikidataid} {strname} in person")
                                results2 = cursor3.fetchall()
                                row2 = results2[0]
                                strnameperson = row2['NAME']
                                straliasesperson = row2['ALIASES']
                                strinstanceofperson = row2['INSTANCE_OF']
                                strwikipediaprofilepathperson = row2['WIKIPEDIA_PROFILE_PATH']
                                arrpersoncouples = {}
                                if strname != "" and (strnameperson == "" or strnameperson is None):
                                    arrpersoncouples["NAME"] = strname
                                if straliases != "" and (straliasesperson == "" or straliasesperson is None):
                                    arrpersoncouples["ALIASES"] = straliases
                                if strinstanceofid != "" and (strinstanceofperson == "" or strinstanceofperson is None):
                                    arrpersoncouples["INSTANCE_OF"] = strinstanceofid
                                if strimagepath != "" and (strwikipediaprofilepathperson == "" or strwikipediaprofilepathperson is None):
                                    arrpersoncouples["WIKIPEDIA_PROFILE_PATH"] = strimagepath
                                if arrpersoncouples:
                                    strsqltablename = "T_WC_WIKIDATA_PERSON_V1"
                                    strsqlupdatecondition = f"ID_WIKIDATA = '{strwikidataid}'"
                                    cp.f_sqlupdatearray(strsqltablename,arrpersoncouples,strsqlupdatecondition,1)
                            # After moving the item to person, we can delete it from T_WC_WIKIDATA_ITEM_V1
                            strsqldelete = "DELETE FROM T_WC_WIKIDATA_ITEM_V1 WHERE ID_WIKIDATA = '" + strwikidataid + "' "
                            print(f"{strsqldelete}")
                            cursor3.execute(strsqldelete)
                            conn.commit()
                if intindex == 111:
                    # T_WC_WIKIDATA_ITEM_PROPERTY de duplication
                    cp.f_setservervariable("strsparqlcrawleritemsdedupcurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
                    strsql = ""
                    strsql += "SELECT * FROM T_WC_WIKIDATA_ITEM_PROPERTY ORDER BY ID_WIKIDATA, ID_PROPERTY, ID_ITEM "
                    #strsql += "LIMIT 500 "
                    if strsql != "":
                        print(strsql)
                        cursor.execute(strsql)
                        lngrowcount = cursor.rowcount
                        print(f"{lngrowcount} lines")
                        strwikidataidprev = ""
                        strpropertyidprev = ""
                        stritemidprev = ""
                        results = cursor.fetchall()
                        for row3 in results:
                            strwikidataid = row3['ID_WIKIDATA']
                            strpropertyid = row3['ID_PROPERTY']
                            stritemid = row3['ID_ITEM']
                            if strwikidataid == strwikidataidprev and strpropertyid == strpropertyidprev and stritemid == stritemidprev:
                                #This is a duplicate record
                                lngrowid = row3['ID_ROW']
                                strsqldelete = "DELETE FROM T_WC_WIKIDATA_ITEM_PROPERTY WHERE ID_ROW = " + str(lngrowid)
                                print(f"{strsqldelete}")
                                cursor3.execute(strsqldelete)
                                conn.commit()
                            strwikidataidprev = strwikidataid
                            strpropertyidprev = strpropertyid
                            stritemidprev = stritemid
                #cp.f_setservervariable("strsparqlcrawlercurrentsql","","Current SQL query in the SPARQL Wikidata crawler",0)
                cp.f_setservervariable("strsparqlcrawlercurrentvalue","","Current value in the current Wikidata SPARQL crawler",0)
                cp.f_setservervariable("strsparqlcrawleritemscurrentprocess","","Current process in the Wikidata SPARQL crawler",0)
            strcurrentprocess = ""
            cp.f_setservervariable("strsparqlcrawlercurrentprocess",strcurrentprocess,"Current process in the Wikidata SPARQL crawler",0)
            strnow = datetime.now(cp.paris_tz).strftime("%Y-%m-%d %H:%M:%S")
            cp.f_setservervariable("strsparqlcrawlerenddatetime",strnow,"Date and time of the Wikidata SPARQL crawler ending",0)
            # Calculate total runtime and convert to readable format
            end_time = time.time()
            strtotalruntime = int(end_time - start_time)  # Total runtime in seconds
            cp.f_setservervariable("strsparqlcrawlertotalruntimesecond",str(strtotalruntime),strtotalruntimedesc,0)
            readable_duration = cp.convert_seconds_to_duration(strtotalruntime)
            cp.f_setservervariable("strsparqlcrawlertotalruntime",readable_duration,strtotalruntimedesc,0)
            print(f"Total runtime: {strtotalruntime} seconds ({readable_duration})")
            
    print("Process completed")
except pymysql.MySQLError as e:
    print(f"❌ MySQL Error: {e}")
    conn = getattr(cp, "connectioncp", None)
    if conn is not None and getattr(conn, "open", False):
        conn.rollback()
