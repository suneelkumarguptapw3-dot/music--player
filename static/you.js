

;
create_track_grid("/api/history/tracks",document.querySelector(".history"));
let l = 
create_track_grid("/api/tracks/liked",document.querySelector(".liked-tracks"));

window.parent["you_page"] = document;
window.parent.addEventListener("load", () => {
    document.body.style.setProperty('--bg-url', `url('${window.parent.bg_img || "/static/image.jpeg"}')`);

});
document.body.style.setProperty('--bg-url', `url('${window.parent.bg_img || "/static/image.jpeg"}')`);
