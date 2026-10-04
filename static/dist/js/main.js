$(document).ready(function () {       
    $(".goTop").click(function(){
        $("html,body").animate({scrollTop:0},900);
        return false;
    }); 
    $(".goTopX").click(function(){
        $("html,body").animate({scrollTop:0},900);
        return false;
    });
});