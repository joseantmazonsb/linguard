import {postJSON, prependAlert} from "./utils.mjs";

export { Wireguard }

class Wireguard {

    static load() {
        const startOrStopIfaceBtn = $(".startOrStopIfaceBtn");
        startOrStopIfaceBtn.click(function (e) {
            const button = e.target;
            const iface = button.value;
            const action = button.innerText;

            const url = "/wireguard/interfaces/" + iface;
            const data = JSON.stringify({"action": action})
            const alertContainer = "wgIfacesHeader";
            const alertType = "danger";
            const loadFeedback = "wgIface-" + iface + "-loading"

            postJSON(url, alertContainer, alertType, loadFeedback, data);
        });

        const restartIfaceBtn = $(".restartIfaceBtn");
        restartIfaceBtn.click(function (e) {
            const iface = e.target.value;
            const action = "restart";

            const url = "/wireguard/interfaces/" + iface;
            const data = JSON.stringify({"action": action})
            const alertContainer = "wgIfacesHeader";
            const alertType = "danger";
            const loadFeedback = "wgIface-" + iface + "-loading"

            postJSON(url, alertContainer, alertType, loadFeedback, data);
        });

        const removeIfaceBtn = $(".removeIfaceBtn");
        removeIfaceBtn.click(function (e) {
            const iface = e.target.id.split("-")[1];
            const url = "/wireguard/interfaces/"+iface+"/remove"
            const alertContainer = "wgIfacesHeader";
            const alertType = "danger";
            $.ajax({
                type: "post",
                url: url,
                success: function () {
                    location.reload();
                },
                error: function(resp) {
                    prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"],
                        alertType);
                    $("#removeIfaceModal").modal("toggle");
                },
            });
        });
    }
}