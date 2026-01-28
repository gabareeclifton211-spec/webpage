document.addEventListener("DOMContentLoaded", () => {

    console.log("JS LOADED"); // Debug confirmation

    // ===============================
    // DOM ELEMENTS
    // ===============================
    const fileList = document.getElementById("file-list");
    const editor = document.getElementById("editor");
    const filenameDisplay = document.getElementById("filename-display");

    const btnNew = document.getElementById("btn-new");
    const btnSave = document.getElementById("btn-save");
    const btnDelete = document.getElementById("btn-delete");
    const btnCancel = document.getElementById("btn-cancel");
    const btnEdit = document.getElementById("btn-edit");

btnEdit.onclick = () => {
    if (!currentFile) return;
    mode = "edit";
    editor.disabled = false;
    updateToolbar();
};


    // ===============================
    // APP STATE
    // ===============================
    let currentFile = null;
    let mode = "view"; // view | edit | new

    // ===============================
    // LOAD FILE LIST
    // ===============================
    function loadFileList() {
        fetch("/text/api/list")
            .then(res => res.json())
            .then(data => {
                fileList.innerHTML = "";

                data.files.forEach(filename => {
                    const div = document.createElement("div");
                    div.className = "file-item";
                    div.textContent = filename;

                    div.onclick = () => selectFile(filename);

                    if (filename === currentFile) {
                        div.classList.add("active");
                    }

                    fileList.appendChild(div);
                });
            });
    }

    // ===============================
    // SELECT FILE
    // ===============================
    function selectFile(filename) {
        fetch(`/text/api/load/${filename}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === "ok") {
                    currentFile = filename;
                    mode = "view";

                    filenameDisplay.textContent = filename;
                    editor.value = data.content;
                    editor.disabled = true;

                    updateToolbar();
                    loadFileList();
                }
            });
    }

    // ===============================
    // NEW FILE
    // ===============================
    btnNew.onclick = () => {
        mode = "new";
        currentFile = null;

        filenameDisplay.textContent = "New File";
        editor.value = "";
        editor.disabled = false;

        updateToolbar();
        loadFileList();
    };

    // ===============================
    // SAVE FILE
    // ===============================
    btnSave.onclick = () => {
        const content = editor.value;

        // NEW FILE SAVE
        if (mode === "new") {
            const name = prompt("Enter a filename:");

            if (!name) return;

            fetch("/text/api/new", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filename: name,
                    content: content
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "ok") {
                    currentFile = data.filename;
                    mode = "view";
                    filenameDisplay.textContent = currentFile;
                    editor.disabled = true;
                    updateToolbar();
                    loadFileList();
                } else {
                    alert(data.message);
                }
            });

        // EDIT EXISTING FILE
        } else if (mode === "edit") {
            fetch("/text/api/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filename: currentFile,
                    content: content
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "ok") {
                    mode = "view";
                    editor.disabled = true;
                    updateToolbar();
                    loadFileList();
                }
            });
        }
    };

    // ===============================
    // DELETE FILE
    // ===============================
    btnDelete.onclick = () => {
        if (!currentFile) return;

        if (!confirm(`Delete "${currentFile}"?`)) return;

        fetch(`/text/api/delete/${currentFile}`, {
            method: "DELETE"
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === "ok") {
                currentFile = null;
                editor.value = "";
                filenameDisplay.textContent = "No file selected";
                editor.disabled = true;
                mode = "view";
                updateToolbar();
                loadFileList();
            }
        });
    };

    // ===============================
    // CANCEL EDIT
    // ===============================
    btnCancel.onclick = () => {
        if (currentFile) {
            selectFile(currentFile);
        } else {
            editor.value = "";
            filenameDisplay.textContent = "No file selected";
            editor.disabled = true;
            mode = "view";
            updateToolbar();
        }
    };

    // ===============================
    // ENTER EDIT MODE (DOUBLE CLICK)
    // ===============================
    editor.addEventListener("dblclick", () => {
        if (!currentFile) return;
        mode = "edit";
        editor.disabled = false;
        updateToolbar();
    });

    // ===============================
    // TOOLBAR LOGIC
    // ===============================
    function updateToolbar() {
    btnSave.classList.add("hidden");
    btnDelete.classList.add("hidden");
    btnCancel.classList.add("hidden");
    btnEdit.classList.add("hidden");

    if (mode === "view" && currentFile) {
        btnEdit.classList.remove("hidden");
        btnDelete.classList.remove("hidden");
    }

    if (mode === "edit" || mode === "new") {
        btnSave.classList.remove("hidden");
        btnCancel.classList.remove("hidden");
    }
}


    // ===============================
    // INITIALIZE
    // ===============================
    loadFileList();
    updateToolbar();

});
