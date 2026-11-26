
const menu_template = document.getElementById("context-menu-template");

document.addEventListener("click", close_menu);
window.addEventListener("scroll", close_menu, true); // true also catches the scrolling .tracks row


create_track_grid("/api/tracks?start=0&end=32",document.querySelector(".tracks"))
create_album_grid("/api/album?start=0&end=35",document.querySelector(".albums"))
create_track_grid("/api/history/tracks?start=0&end=9",document.querySelector(".continue-listening"))

window.parent["home_page"] = document;
window.parent.addEventListener("load", () => {
    document.body.style.setProperty('--bg-url', `url('${window.parent.bg_img || "/static/image.jpeg"}')`);

});
document.body.style.setProperty('--bg-url', `url('${window.parent.bg_img || "/static/image.jpeg"}')`);
