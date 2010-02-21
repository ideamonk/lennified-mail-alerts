Cufon.replace(".GoodDog");

function showDialog(id){
    $(".dialog").fadeOut("fast");
    $("#" + id).fadeIn("fast");
}

$(document).ready( function(){
    $("body").click( function(){
            $(".dialog").fadeOut("fast");
    });

    setTimeout('step_animate()',1500);
});

function step_animate(){
    $(".step_on").stop().animate({paddingLeft:'40px'}, 1500);
}