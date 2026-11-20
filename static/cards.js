function createTrackCard(track, { element = "div", href, target, includeInfo = false } = {}) {
    const card = document.createElement(element);
    card.className = "track";
    if (href !== undefined) {
        card.href = href;
    }
    if (target !== undefined) {
        card.target = target;
    }
    if (includeInfo) {
        card.info = track;
    }

    const image = document.createElement("img");
    image.src = track["thumbnail"];
    image.setAttribute("loading","lazy");
    const details = document.createElement("div");
    const title = document.createElement("div");
    const artists = document.createElement("div");
    title.innerText = track["title"];
    artists.innerText = track["artists"];
    details.append(title, artists);
    card.append(image, details);
    return card;
}

function createAlbumCard(album) {
    const card = document.createElement("button");
    card.href = `/album-page/${album}`;
    card.className = "album";
    
    const image = document.createElement("img");
    image.src = `/api/thumbnail/${album}.webp`;
    image.setAttribute("loading","lazy");
    const title = document.createElement("div");
    const play=document.createElement("button");
    play.className="play";
    card.playBtn=play;
    play.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" height="40px" width="40px" fill="#e3e3e3"><path d="M15.92,27.22L27.22,20L15.92,12.78V27.22ZM20,36.67q-3.43,0-6.47-1.31T8.22,31.78T4.65,26.47T3.33,20q0-3.46 1.31-6.5T8.22,8.21t5.31-3.56T20,3.33q3.46,0 6.5,1.31t5.29,3.56t3.56,5.29T36.67,20q0,3.43-1.31,6.47t-3.56,5.31T26.5,35.35T20,36.67Zm0-2.78q5.81,0 9.85-4.06T33.89,20q0-5.81-4.04-9.85T20,6.11q-5.78,0-9.83,4.04T6.11,20q0,5.78 4.06,9.83T20,33.89ZM20,20Z"/></svg>`;
    title.innerText = album;
    card.append(image, title,play);
    return card;
}
