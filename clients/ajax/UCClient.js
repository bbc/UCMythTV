/*
Copyright 2011 British Broadcasting Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

*/

// This is a simple javascript client for UC which will work
// with server version 0.6.0

var uc_base_uri_default = "http://localhost:48875";
var uc_base_uri = uc_base_uri_default;

var sources_by_ID = new Array();

var current_sid = "__UNKNOWN_SOURCE";
var current_pid = "";
var current_volume = 0.0;

var output_rref = "/uc/outputs/0";

var output_id = "0";

// This is a useful assistive function to call another function 
// whenever the enter key is pressed.
function submitenter(e,callable)
{
    var keycode;
    if (window.event) keycode = window.event.keyCode;
    else if (e) keycode = e.which;
    else return true;
    
    if (keycode == 13) {
	callable();
	return false;
    }
    else
	return true;
}

// This function connects to the server, takes no paramters, but 
// extracts the pairing-code from the value of the text field.
function connect_to_server() {
    $('#enter-pairing-code-dialogue').dialog("close");
    $('#connecting-status-dialogue').dialog("open");
    
    uc_base_uri = PairingCode.decode($('#pairing-code').val()).url;

    make_initial_connection();    
};

// This function is called whenever a connection to the server is 
// canceled.
function cancel_connection() {
    uc_base_uri = uc_base_uri_default;
    $('#connecting-status-dialogue').dialog("close");
    $('#enter-pairing-code-dialogue').dialog("open");
};


// This function makes the initial connection to the UC Server, and when this is
// done it removes the connecting dialogue and shows the main UI.
//
// It does this via the passing of cascaded callbacks. Probably not a very elegant way
// of doing this, but it works. In this case process_base_resource will be called if the request
// is succesful, and it is passed a method telling it what other requests to make after processing
// the base resource:
//   First update_sources, then update_output, then update_programme, and if that works then
// finish_connecting and start_events_loop get called.
function make_initial_connection() {
    $.ajax({
	    type: 'GET',
		url: uc_base_uri + "/uc",
		success: function(xml) { 
		if (process_base_resource(xml)) {
		    update_sources(function () {
			    update_output(function() {
				    update_programme("0",function() {
					    finished_connecting();
					    start_events_loop();
					});				
				});
			});
		} else {
		    cancel_connection();
		}
	    },   		   
		error: cancel_connection,		
		});
};

// This method is called when a connection to the server is correctly established, and it closes the
// dialogue boxes and shows the client controls
function finished_connecting() {
    $('#connecting-status-dialogue').dialog("close");
    $('#server-status').show();
};

// This function processes the base resource, returning true if successful, and false otherwise.
function process_base_resource(xml) {
    good = true;
    
    $('ucserver',xml).each(function() {

	    // here we extract the version and check it against the version this client was designed for

	    version = $(this).attr('version');
	    if(!version.match(/^0\.6\.0$/)) {
		alert("Server Version is incompatible with this client! Canceling connection");
		good = false;
	    } else if ($(this).attr('security-scheme') == 'true') {
		alert("WARNING: This server requires the security-scheme, which this client does not support! Canceling connection");
		good = false;
	    }
	    
	    // Next we check that the server implements the resources this client needs	    
	    events = false;
	    sources = false;
	    source_lists = false;
	    outputs = false;
	    
	    $('resource',this).each(function() {
		    rref = $(this).attr('rref');
		    if (rref == 'uc/events')
			events = true;
		    else if (rref == 'uc/sources') 
			sources = true;
		    else if (rref == 'uc/source-lists')
			source_lists = true;
		    else if (rref == 'uc/outputs')
			outputs = true;				    
		});

	    if (!(events && sources && source_lists && outputs)) {
		alert("WARNING: This server doesn't implement some features required for full use of this client!");
	    }
	});   

    return good;
}

// This method grabs a list of sources from the server and puts them into the select element so that we can 
// pick from them when asking to change source.
function update_sources(onpass) {
    sources_by_ID = new Array();
    $(".source-id-option").detach();
    $.ajax({
	    type: "GET",
		url: uc_base_uri + "/uc/source-lists/uc_default",
		success: function(xml) {
		parse_sources(xml);
		onpass();
	    },		
	});
};

// This method is called when the request to uc/source-lists/uc_default returns
//
// It fills out the sources_by_ID global asosciative array with source information
// indexed by source-id, and also adds an entry to the select element for each source
//
function parse_sources(xml) {
    $("source",xml).each( function () {
	    sid = escape_id($(this).attr("sid"));
	    name = $(this).attr("name");
	    lcn = $(this).attr("lcn");
	    sources_by_ID[sid] = new Array();
	    sources_by_ID[sid]["sid"]   = $(this).attr("sid");
	    sources_by_ID[sid]["name"] = name;
	    sources_by_ID[sid]["lcn"]  = lcn;	 
	    sources_by_ID[sid]["live"] = false;
	    if ($(this).attr("live") == "true")
		sources_by_ID[sid]["live"] = true;
	    if (lcn != undefined)
		$('#sources').append('<option role="option" class="source-id-option" value="' + sid
				     + '">' + lcn + " -- " + name
				     + '</option>');	    
	    else
		$('#sources').append('<option role="option" class="source-id-option" value="' + sid
				     + '">' + name
				     + '</option>');	    		
	});
};






// This method fetches the information from uc/outputs/main to see what the box is currently presenting
function update_output(onpass) {
    $.ajax({ type: "GET",
		url: uc_base_uri + "/uc/outputs/main",
		success: function(xml) {
		parse_output(xml);
		onpass();
	    },
		});
};

// When a request to uc/outputs/{id} returns this method handles the response, filling out the necessary
// details on in the areas of the html which are designed to hold these details
function parse_output(xml) {
    var sid = "";   
    var cid = "";

    // This is the deafault message if the sid isn't recognised
    name = "UNKNOWN SOURCE";

    prog = false;
    app = false;
    
    $("response",xml).each(function() {
	    output_rref = $(this).attr("resource");
	    $("output",this).each(function() {
		    $("settings",this).each(function() {
			    volume = $(this).attr("volume");
			});
		    $("programme",this).each(function() {
			    prog = true;
			    sid = escape_id($(this).attr("sid"));
			    cid = escape_id($(this).attr("cid"));
			});	    
		    $("app",this).each(function() {
			    app = true;
			    sid = escape_id($(this).attr("sid"));
			    cid = escape_id($(this).attr("cid"));
			});			    
		});
	});

    current_sid = sid;
    current_cid = cid;
    current_volume = volume;

    if (prog || app) {
	name = sources_by_ID[sid]["name"];
    }

    $('#VOLUME_DIV').hide();
    $("#sourcesection").hide();

    $("#sources").val(sid);

    $("#SOURCE_HEADER_text").text("Currently Presenting ");
    $("#current_source").text(name);

    $("#sourcesection").show();


    // The volume section remains hidden if there is no volume to control
    $('#VOLUME_DIV').hide();
    if (volume != undefined) {
	$('#VOLUME_DIV').show();

	$('#VOLUME_LABEL').text("Volume Now:");
	$('#VOLUME_CURRENTLY').text("" + parseInt(volume*100.0) + "%");

	val = parseInt(10.0*volume);
	$('#VOLUME_INPUT').val(val);
    }
};



// This method fetches content information from the uc/search/outputs/{id} resource
function update_programme(id,onpass) {
    $.ajax({ type: "GET",
		url: uc_base_uri + "/uc/search/outputs/" + id + "?results=1",
		success: function(xml) {
		parse_programme(xml);
		onpass();
	    },
		});
};

// When a request to uc/search/outputs/{id} returns this method processes the results
function parse_programme(xml) {
    synopsis = "NO DESCRIPTION";

    var start;
    var end;
    var title;

    $("results",xml).each(function() {
	    $("content",this).each(function() {
		    title    = $(this).attr("title");
		    start    = $(this).attr("start");
		    duration = $(this).attr("duration");
		    $("synopsis",this).each(function() {
			    synopsis = $(this).text();
			});
		});
	});    

    if (title == undefined) {
	title = "UNKNOWN CONTENT";
    }

    $("#nowsection").hide();

    $("#NOW_SHOWING_text").text("Now Showing:");
    $("#now-programme").text(title);

    var time;

    if (start != undefined) {
	time = extract_time(start);
	if (duration != undefined) {
	    time += " until " + extract_time_plus(start,parseInt(duration));
	}
    }

    $('#NOW_TIME_HEADER').hide();

    // if the time is undefined then the time section remains hidden
    if (time != undefined) {
	$('#NOW_TIME_HEADER').show();	

	$("#NOW_TIME_HEADER_text").text("Time:");
	$("#now-time").text(time);
    }
  
    $("#NOW_DESCRIPTION_HEADER").text("Description");
    $("#now-description").text(synopsis);

    $("#nowsection").show();
};


// This method starts the event listening loop. Since we don't have multiple threads this is all handled by asynchronous HTTP requests
// 
// A request is sent, the notification-id is extracted (by parse_events) and then a normal update_events request is made. On an error
// we attempt to restart the loop.
var notification_id = "";
function start_events_loop() {
    notification_id = "";
    $.ajax({ type: "GET",
		url: uc_base_uri + "/uc/events",
		success: function(xml) {
		parse_events(xml);
		update_events();
	    },
		error: start_events_loop,
		});
};

// This method is called whenever a new request needs to be made for events in the normal course of operation. On a succesful response
// it parses the response and then calls itself again, on an error we attempt to restart the loop.
function update_events() {
    $.ajax({ type: "GET",
		url: uc_base_uri + "/uc/events?since=" + notification_id,
		success: function(xml) {
		parse_events(xml);
		update_events();
	    },
		error: start_events_loop,
		});
};

// This method parses the responses from uc/events, it extracts changes to the output data, and also reads in the new
// notification-id and stores it.
//
// If the output has changed then we call update_output, and tell it to call update_programme if it succeeds.
function parse_events(xml) {
    $("events",xml).each(function() {
	    notification_id = $(this).attr("notification-id");

	    $("resource",this).each(function() {
		    rref = $(this).attr("rref");
		    if (rref == output_rref) {
			update_output(function() {
				update_programme("0",function() {});
			    });
		    }
		});
	});
};


// This method is called to change the source on the box it is automatically called by the user pressing the GO button
//
// If the source selected is live then this method immediately makes an HTTP request to change source, if not then it
// runs update_programmes telling it to run chow_programmes_dialogue when it's finished its requests.
//
// This displays a list of content to choose from.
var fetched_programmes;
var all_programmes_fetched = false;
var current_offset = 0;
var page_size = 10;

function change_source() {
    sid = $("#sources").val();

    if (sources_by_ID[sid]["live"]) {
	$.ajax({ type: "POST",
		    url: uc_base_uri + "/"  + output_rref + "?sid=" + unescape_id(sid),
		    });
	return;
    }

    fetched_programmes = new Array();
    current_offset = 0;
    all_programmes_fetched = false;
    update_programmes(sid,0,page_size*4,function() {
	    show_programmes_dialogue(sid);
	});
}



// This method ust changes the volume of the output, it's pretty direct and simple
function change_volume() {
    volume = parseInt($('#VOLUME_INPUT').val())/10.0;

    data ='<response resource="'
	+ output_rref
	+ '"><settings volume="'
	+ volume
	+ '"/></response>\r\n';

    $.ajax({ type: "PUT",
		url: uc_base_uri + "/"  + output_rref + "/settings",
		data: data,
		});
}



// this method makes a request to uc/search for the specified source and
// places the content into the select-programmes dialogue. When it finishes it runs
// the callback it's given
function update_programmes(sid,offset,results,onfill) {
    $.ajax({ type: "GET",
		url: uc_base_uri + "/uc/search/sources/" + unescape_id(sid) + "?offset=" 
		+ offset
		+ "&results="
		+ results,
		success: function(xml) {
		parse_programmes(xml,sid,offset,results);
		onfill();
	    },
		});
};

// This method parse the response from a request to uc/search/sources/{sids}.
// It fills out a global array of content (called fetched_programmes) with the details
// of the individual pieces of content (this array is used to populate the content
// selection dialogue box)
function parse_programmes(xml,sid,offset,results) {
    i=0;

    var cid;
    var name;

    $("results",xml).each(function() {	    
	    more = $(this).attr("more");	    
	    $("content",this).each(function() {
		    cid = escape_id($(this).attr("cid"));
		    name= $(this).attr("title");

		    fetched_programmes[offset + i] = new Array();
		    fetched_programmes[offset + i]['cid']  = cid;
		    fetched_programmes[offset + i]['sid']  = sid;
		    fetched_programmes[offset + i]['name'] = name;
		    i += 1;
		});
	    if (more == "false") {
		all_programmes_fetched = true;	    
	    } else {
		all_programmes_fetched = false;	    
	    }
	});
};


// This method shows a dialogue box used to select content to tune to. It pages the data and allows the user to 
// skip through it with next and previous buttons. Requests for more content to fill new pages with are made in the 
// background whilst the current page is showing.
function show_programmes_dialogue(sid) {
    $('#select-programme-dialogue').dialog("close");

    max = current_offset + page_size - 1;
    if (max >= fetched_programmes.length) {
	max = fetched_programmes.length - 1;
    }

    $('#select-programme-dialogue').dialog("option","title","Please select programme (showing " + (current_offset + 1) + " to " + (max + 1) + ")");

    $("#programme-button-list").empty();
    for (i=0; i < page_size && current_offset + i < fetched_programmes.length; i++) {
	if (fetched_programmes[current_offset + i] != undefined) {
	    $("#programme-button-list").append('<li><button id="PROG_' 
					       + (current_offset + i) 
					       + '">'
					       + (current_offset + i + 1)
					       + " -- "
					       + fetched_programmes[current_offset + i]['name'] 
					       + "</button></li>");
	    $("#PROG_" + (current_offset + i)).button().click(function() {
		    $('#select-programme-dialogue').dialog("close");
		    n = (/PROG_(.+)/.exec($(this).attr('id')))[1];
		    cid = fetched_programmes[n]["cid"]

		    $("#programme-button-list").empty();

		    $.ajax({ type: "POST",
				url: uc_base_uri + "/"  + output_rref + "?sid=" + unescape_id(sid) + "&cid=" + unescape_id(cid),
				});
		});
	}
    }

    $("#programme-dialogue-control-buttons").empty();
    $("#programme-dialogue-control-buttons").append(
'<button id="prev-programme-screen" tabindex="0">Previous</button>'
						    );
    $("#programme-dialogue-control-buttons").append(
'<button id="next-programme-screen" tabindex="0">Next</button>'
						    );

    if (current_offset < page_size) {
	$("#prev-programme-screen").button({disabled: true});
    } else {
	$("#prev-programme-screen").button({disabled: false}).click(function() {
		current_offset -= page_size;
		show_programmes_dialogue(sid);
	    });
    }

    if (current_offset + page_size >= fetched_programmes.length) {
	$("#next-programme-screen").button({disabled: true});
	if (!all_programmes_fetched) {
	    update_programmes(sid,fetched_programmes.length,20, function() {
		    $("#next-programme-screen").button({disabled: false}).click(function() {
			    current_offset += page_size;
			    show_programmes_dialogue(sid);
			});
		});
	}	
    } else {
	$("#next-programme-screen").button({disabled: false}).click(function() {
		current_offset += page_size;
		show_programmes_dialogue(sid);
	    });
    }

    $('#select-programme-dialogue').dialog("open");
};


// These functions work around deficiencies in what characterers can be included in HTML IDs
function escape_id(id) {
    return id.replace(/__/,"__underscore").replace(/\./g,"__dot").replace(/\%/g,"__percent");
}
function unescape_id(id) {
    return id.replace(/__percent/g,"%").replace(/__dot/g,".").replace(/__underscore/,"__");
}


// This code extracts times from a ISO date string
function extract_time(iso) {
    match = /(\d\d\d\d)-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(.\d+)?.+/.exec(iso);

    return match[4] + ":" + match[5];
};

// This one takes an iso date string and a duration in seconds and returns the end time
function extract_time_plus(iso,duration) {
    match = /(\d\d\d\d)-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(.\d+)?.+/.exec(iso);
    
    end = parseInt(match[4])*3600 + parseInt(match[5])*60 + parseInt(match[6]) + duration;
    return parseInt(end/3600).toPrecision(2) + ':' + (parseInt(end/60)%60).toPrecision(2);
}


var PairingCode = {

	//This function is used to decode a pairing code.
	decode : function decoder(code) {

		var current_code = "";
		var code_index = 0;
		var overflow_bits = 0;
		var current_multiplier = 1;

		var code_reset = function(code) {
			current_code = code;
			code_index = code.length - 1;
			overflow_bits = 0;
			current_multiplier = 1;
		};

        var stringChars = new Array(
        '0','1','2','3','4','5','6','7',
        '8','9','A','B','C','D','E','F',
        'G','H','J','K','M','N','P','Q',
        'R','S','T','V','W','X','Y','Z'
        );

		var get_codebits = function(bits) {

		    while (code_index >= 0 && (current_multiplier % (1 << bits)) != 0) {
			digit = stringChars.indexOf(current_code.charAt(code_index));
			code_index = code_index - 1;	
			overflow_bits = overflow_bits + current_multiplier*digit;
			current_multiplier = current_multiplier*32;
		    }
		    
		    output = overflow_bits % (1 << bits);
		    overflow_bits = overflow_bits >>> bits;
		    current_multiplier = current_multiplier >>> bits;
		    return output;
		};

		var signal;
		var SSS;
		var A;
		var B;
		var C;
		var D;
		var port;

		code_reset(code);
		    
		var signal = get_codebits(2);

		if (signal%2 == 1) {
			throw "error in pairing code parsing";
		}

		if ((signal >> 1) == 1) {
			SSS = get_codebits(8);
		}

		signal = get_codebits(2);

		if (signal == 0) {
			A = 192;
			B = 168;

			signal = get_codebits(2);

			if (signal == 0) {
				C = 0;
			} else if (signal == 1) {
				C = 1;
			} else if (signal == 2) {
				C = 2;
			} else {
				C = get_codebits(8);
			}

			D = get_codebits(8);
		} else if (signal == 1) {
			A = 172;
			D = get_codebits(8);
			C = get_codebits(8);
			B = get_codebits(4) + 16;
		} else if (signal == 2) {
			A = 10;
			D = get_codebits(8);
			C = get_codebits(8);
			B = get_codebits(8);
		} else {
			D = get_codebits(8);
			C = get_codebits(8);
			B = get_codebits(8);
			A = get_codebits(8);
		}

		signal = get_codebits(1);
		if (signal == 0) {
			port = 48875;
		} else {
			port = get_codebits(16);
		}

		if (get_codebits(16) != 0) {
			throw "error in pairing code parsing";
		}

		return {
			url: "http://" + A + "." + B + "." + C + "." + D + ":" + port,
			sss: SSS,
			};

	},



};






// The following is the "main" code, executed automatically on page-load. It sets up the dialogue box and control behaviours as needed.

$(function() {
	$('#enter-pairing-code-dialogue').dialog({
		autoOpen: true,
		    width: 600,
		    modal: true,
		    buttons: {
		    "OK": function() {
			connect_to_server();
		    }
		},
		    title: "Not Connected to Server"
		    });	
	$('#connecting-status-dialogue').dialog({
		autoOpen: false,
		    width: 600,
		    modal: true,
		    title: "Please Wait, Connecting to Server ...",
		    buttons: {
		    "Cancel": function() {
			cancel_connection();
		    }
			},
		    closeOnEscape: false,
	    });
	$("#change_source_button").click(function(e) {
		change_source();
	    });
	$('#change_volume_button').click(function(e) {
		change_volume();
	    });       
	$("#sources").keypress(function(e) { 
		return submitenter(e,change_source);
	    });
	$("#VOLUME_INPUT").keypress(function(e) {
		return submitenter(e,change_volume);
	    });
	$('#select-programme-dialogue').dialog({
		autoOpen: false,
		    width: 600,
		    modal: true,
		    title: "Please Select Programme",
		    closeOnEscape: false,
	    });
    });
