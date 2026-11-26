let open_menu = null;
function close_menu() {
    if (open_menu) {
        open_menu.style.display = "none";
        open_menu = null;
    }
}
function createContextMenu() {
    const nav = document.createElement("nav");
    nav.className = "context-menu";

    nav.innerHTML = `
        <ul>
            <li>
                <button data-action="play">
                    <svg xmlns="http://www.w3.org/2000/svg"
                        height="24px" viewBox="0 -960 960 960" width="24px"
                        fill="#e3e3e3">
                        <path d="m383-310 267-170-267-170v340Zm97 230q-82 0-155-31.5t-127.5-86Q143-252 111.5-325T80-480q0-83 31.5-156t86-127Q252-817 325-848.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 82-31.5 155T763-197.5q-54 54.5-127 86T480-80Zm0-60q142 0 241-99.5T820-480q0-142-99-241t-241-99q-141 0-240.5 99T140-480q0 141 99.5 240.5T480-140Zm0-340Z"/>
                    </svg>
                    <div>Play</div>
                </button>
            </li>

            <li>
                <button data-action="queue">
                    <svg xmlns="http://www.w3.org/2000/svg"
                        height="24px" viewBox="0 -960 960 960" width="24px"
                        fill="#e3e3e3">
                        <path d="M440-360h80v-120h120v-80H520v-120h-80v120H320v80h120v120ZM320-120v-80H160q-33 0-56.5-23.5T80-280v-480q0-33 23.5-56.5T160-840h640q33 0 56.5 23.5T880-760v480q0 33-23.5 56.5T800-200H640v80H320ZM160-280h640v-480H160v480Zm0 0v-480 480Z"/>
                    </svg>
                    <div>Add To Queue</div>
                </button>
            </li>

            <li>
                <button data-action="play_next">
                    <svg xmlns="http://www.w3.org/2000/svg"
                        height="24px" viewBox="0 -960 960 960" width="24px"
                        fill="#e3e3e3">
                        <path d="m780-60-60-60 120-120-120-120 60-60 180 180L780-60Zm-460-60v-80H160q-33 0-56.5-23.5T80-280v-480q0-33 23.5-56.5T160-840h640q33 0 56.5 23.5T880-760v280h-80v-280H160v480h520v80h-80v80H320Zm120-240h80v-120h120v-80H520v-120h-80v120H320v80h120v120Zm-280 80v-480 480Z"/>
                    </svg>
                    <div>Play Next</div>
                </button>
            </li>

            <li>
                <button data-action="go_album">
                    <svg xmlns="http://www.w3.org/2000/svg"
                        height="24px" viewBox="0 -960 960 960" width="24px"
                        fill="#e3e3e3">
                        <path d="M480-300q75 0 127.5-52.5T660-480q0-75-52.5-127.5T480-660q-75 0-127.5 52.5T300-480q0 75 52.5 127.5T480-300Zm-28.5-151.5Q440-463 440-480t11.5-28.5Q463-520 480-520t28.5 11.5Q520-497 520-480t-11.5 28.5Q497-440 480-440t-28.5-11.5ZM480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"/>
                    </svg>
                    <div>Go to Album</div>
                </button>
            </li>

            <li>
                <button data-action="go_artist">
                    <svg xmlns="http://www.w3.org/2000/svg"
                        height="24px" viewBox="0 -960 960 960" width="24px"
                        fill="#e3e3e3">
                        <path d="M740-560h140v80h-80v220q0 42-29 71t-71 29q-42 0-71-29t-29-71q0-42 29-71t71-29q8 0 18 1.5t22 6.5v-208ZM120-160v-112q0-35 17.5-63t46.5-43q62-31 126-46.5T440-440q42 0 83.5 6.5T607-414q-20 12-36 29t-28 37q-26-6-51.5-9t-51.5-3q-57 0-112 14t-108 40q-9 5-14.5 14t-5.5 20v32h321q2 20 9.5 40t20.5 40H120Zm207-367q-47-47-47-113t47-113q47-47 113-47t113 47q47 47 47 113t-47 113q-47 47-113 47t-113-47Zm169.5-56.5Q520-607 520-640t-23.5-56.5Q473-720 440-720t-56.5 23.5Q360-673 360-640t23.5 56.5Q407-560 440-560t56.5-23.5ZM440-640Zm0 400Z"/>
                    </svg>
                    <div>Go to Artists</div>
                </button>
            </li>
        </ul>
    `;

    return nav;
}
function attach_context_menu(card) {
    const menu = createContextMenu();
    card.appendChild(menu);
    menu.addEventListener("click", (e) => {
        e.stopPropagation();
    });
    menu.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        e.stopPropagation();
    });
    menu.querySelectorAll("button[data-action]").forEach((btn) => {
        btn.addEventListener("click", () => {
            close_menu();

            const fn = card[btn.dataset.action];

            if (fn) fn.call(card);
        });
    });
    card.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        close_menu();
        menu.style.display = "block";
        const viewport = window.visualViewport;
        const width = viewport
            ? viewport.width
            : window.innerWidth;
        const height = viewport
            ? viewport.height
            : window.innerHeight;
        const margin = 8;
        const menuWidth = menu.offsetWidth;
        const menuHeight = menu.offsetHeight;

        // Clamp the cursor position to the visible viewport.
        const x = Math.max(
            margin,
            Math.min(
                event.clientX,
                width - menuWidth - margin
            )
        );
        const y = Math.max(
            margin,
            Math.min(
                event.clientY,
                height - menuHeight - margin
            )
        );
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;
        open_menu = menu;
    });
}

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
    image.setAttribute("loading", "lazy");
    const details = document.createElement("div");
    const title = document.createElement("div");
    const artists = document.createElement("div");
    title.innerText = track["title"];
    artists.innerText = track["artists"];
    details.append(title, artists);
    card.append(image, details);
    let w = Math.floor((track["endpoint"] * 100) / el["duration"]);
    attach_context_menu(card);
    card.innerHTML += `<div class="progress" >
               <div style="width:${w}%"></div>
            </div> `

    return card;
}

function createAlbumCard(album) {
    const card = document.createElement("button");
    card.href = `/album-page/${album}`;
    card.className = "album";

    const image = document.createElement("img");
    image.src = `/api/thumbnail/${encodeURIComponent(album)}.webp`;
    image.setAttribute("loading", "lazy");
    const title = document.createElement("div");
    const play = document.createElement("button");
    play.className = "play";
    card.playBtn = play;
    play.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" height="40px" width="40px" fill="#e3e3e3"><path d="M15.92,27.22L27.22,20L15.92,12.78V27.22ZM20,36.67q-3.43,0-6.47-1.31T8.22,31.78T4.65,26.47T3.33,20q0-3.46 1.31-6.5T8.22,8.21t5.31-3.56T20,3.33q3.46,0 6.5,1.31t5.29,3.56t3.56,5.29T36.67,20q0,3.43-1.31,6.47t-3.56,5.31T26.5,35.35T20,36.67Zm0-2.78q5.81,0 9.85-4.06T33.89,20q0-5.81-4.04-9.85T20,6.11q-5.78,0-9.83,4.04T6.11,20q0,5.78 4.06,9.83T20,33.89ZM20,20Z"/></svg>`;
    title.innerText = album;
    card.append(image, title, play);
    return card;
}


function create_track_grid(url, container) {
    fetch(url).then(response => response.json()).then(data => {
        container["playlist"]=data;
        let n = 0;
        if (window.self != window.top) {
            let p = true;
            for (el of data) {
                let id = el["id"];
                let card = createTrackCard(el, { includeInfo: true });
                card.play = function () { this.click(); };
                card.queue = function () { window.parent.add_queue(this.info); };
                card.play_next = function () { window.parent.add_next(this.info); };
                card.go_album = function () { location.href = `/album-page/${this.info["album"]}`; };
                card.go_artist = function () { /* not implemented yet, same as before */ };
                card.addEventListener("click", () => {
                    
                    window.parent.route_parent(id);
                    window.parent.fetch_metadata(id);
                });
                attach_context_menu(card);
                container.appendChild(card);
                n++;
            };
            return;
        }
        for (el of data) {
            let id = el["id"];
            let card = createTrackCard(el, {
                element: "a",
                href: `/player?song=${id}`,
                target: "_parent"
            });
            card.addEventListener("contextmenu", (event) => {
                event.preventDefault();
                event.stopPropagation();
            });
            container.appendChild(card);
            n++;
        };
    })
}



function create_album_grid(url,container) {
    fetch(url).then(response => response.json()).then(data => {
        let n = 0;
        if (window.self != window.top) {
            for (el of data) {
                if (n > 32) {
                    break;
                }
                n += 1;
                let card = createAlbumCard(el);
                card.addEventListener("click", () => {
                    location.pathname = card.href;
                })
                card.playBtn.album_name = el;
                card.playBtn.playAll = function () {
                    fetch(`/api/album/${this.album_name}`).then(response => response.json()).then(data => {
                        data.forEach(e => {
                            window.parent.add_next(e);
                        })
                        window.parent.route_parent(data[0]["id"]);
                        window.parent.fetch_metadata(data[0]["id"]);
                    });
                }
                card.playBtn.addEventListener("click", (event) => {
                    event.stopPropagation();
                    event.target.playAll();
                })
                container.appendChild(card);
            };

        } else {
            let n = 0;
            for (el of data) {
                if (n > 32) {
                    break;
                }
                n += 1;
                let card = createAlbumCard(el);
                card.addEventListener("click", () => {
                    location.pathname = card.href;
                })
                card.playBtn.album_name = el;
                card.playBtn.playAll = function () {
                    fetch(`/api/album/${this.album_name}`).then(response => response.json()).then(data => {
                        location.href = `/player?song=${encodeURIComponent(data[0].id)}&album=${encodeURIComponent(data[0].album)}`;
                    });
                }
                card.playBtn.addEventListener("click", (event) => {
                    event.stopPropagation();
                    event.target.playAll();
                })
                container.appendChild(card);
            };
        }

    });
}