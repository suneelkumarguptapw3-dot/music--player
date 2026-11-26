const search_results = document.querySelector(".search-results");
function f(query) {
    search_results.innerHTML = "";
    fetch(`/search?q=${query}`).then(response => response.json()).then(data => {
        let n = 0;
        if (window.self != window.top) {
            for (el of data) {
                if (n >= 52) break;
                let id = el["id"];
                let card = createTrackCard(el, { includeInfo: true });

                card.play = function () { this.click(); };
                card.queue = function () { window.parent.add_queue(this.info); };
                card.play_next = function () { window.parent.add_next(this.info); };
                card.go_album = function () { location.href = `/album-page/${this.info["album"]}`; };
                card.go_artist = function () { /* not implemented yet, same as before */ };

                card.addEventListener("click", (event) => {
                    event.stopPropagation();
                    window.parent.route_parent(id);
                    window.parent.fetch_metadata(id);
                });
                search_results.appendChild(card);
                n++;
            };
            return;
        }
        for (el of data) {
            if (n >= 52) {
                break;
            }
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
            search_results.appendChild(card);
            n++;
        };

    })

}
const search_input = document.getElementById("search-input");
search_input.addEventListener("input", (event) => {
    setTimeout(() => {
        f(event.target.value);
    }, 200);
});
document.getElementById("search-input").addEventListener("focusin", () => {
    document.querySelector(".search-container").classList.add("focused");
})
document.getElementById("search-input").addEventListener("focusout", () => {
    setTimeout(() => {
         document.querySelector(".search-container").classList.remove("focused");
    }, 100);
    search_input.value="";
})