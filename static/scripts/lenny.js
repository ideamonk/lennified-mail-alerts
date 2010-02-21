Cufon.replace(".GoodDog");

function showDialog(id){
    $(".dialog").fadeOut("fast");
    $("#" + id).fadeIn("fast");
}

$(document).ready( function(){
    $("body").click( function(){
            $(".dialog").fadeOut("fast");
    });
});