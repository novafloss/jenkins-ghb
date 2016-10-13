var dashboard = {
    context: {},

    main: function() {
        var mainel = document.getElementById("main");
        mainel.innerHTML = (
            '<header><h1>Jenkins EPO Dashboard</h1></header>' +
            '<article id="body"></article>'
        );
        this.context.h1 = document.getElementsByTagName('h1')[0];
        this.context.body = document.getElementById('body');
        window.addEventListener('popstate', function(event){
            dashboard.route();
        });
        window.addEventListener('hashchange', function(event) {
            dashboard.route();
        });
        this.route();
    },
    route: function() {
        var uri = window.location.hash.slice(2);
        if (!uri) {
            this.repositoriesView();
            this.context.body.className = 'repositories';
        }
        else if (uri.startsWith('/heads/')) {
            this.headsView(uri.slice('/heads/'.length));
            this.context.body.className = 'heads';
        }
        else if (uri.startsWith('/pipeline/')) {
            this.pipelineView(uri.slice('/pipeline/'.length));
            this.context.body.className = 'pipeline';
        }
    },

    pipelineView: function(path) {
        var request = new XMLHttpRequest();
        request.open("GET", "/rest/pipeline/" + path, true);
        request.onreadystatechange = function() {
            if (4 != this.readyState)
                return;

            try {
                var payload = JSON.parse(this.response);
            }
            catch (err) {
                var payload = {message: "JSON Error: " + err, raw: this.response}
            }

            if (200 != this.status) {
                console.log("Erreur: ", payload);
                return;
            }
            dashboard.context.h1.innerHTML = (
                '<span class="head">' +
                payload.repository.owner + '/' +
                payload.repository.name + ' ' +
                payload.ref +
                ':</span> ' +
                '<a href="' + payload.tree_url + '">' +
                '<span class="message">' +
                payload.message_html +
                '</span>' +
                '</a>'
            );
            dashboard.context.body.innerHTML = (
                '<section class="head">' +
                '<p id="diff">' +
                '<span class="files">' + payload.diff.files + ' files changed</span>, ' +
                '<span class="additions">' + payload.diff.additions + ' insertions(+)</span>, ' +
                '<span class="deletions">' + payload.diff.deletions + ' deletions(-)</span>' +
                '</p>' +
                '<canvas id="pipeline"></canvas>' +
                '</section>'
            );
            var canvas = document.getElementById('pipeline');
            dashboard.drawPipeline(
                canvas,
                parseInt(window.getComputedStyle(document.querySelector('#body')).width),
                payload
            );
            window.addEventListener('resize', function() {
                dashboard.drawPipeline(
                    canvas,
                    parseInt(window.getComputedStyle(document.querySelector('#body')).width),
                    payload
                );
            });
        };
        request.send();
    },

    drawPipeline: function(canvas, max_width, payload) {
        canvas.width = max_width;
        var rowSize = parseInt("60pt");
        canvas.height = rowSize * (2 + payload.stages[0].jobs.length)
        var ctx = canvas.getContext("2d");
        var count = payload.stages.length;
        var colors = {
            'success': "#55a532",
            'pending': 'rgb(206, 166, 27)',
            'error': '#F44336',
            'failure': '#F44336',
            'unknown': '#9E9E9E',
        }
        var color = '';
        var colSize = canvas.offsetWidth / count;
        var radius = parseInt("20pt");
        var job_radius = .75 * radius;
        ctx.lineWidth = parseInt("8pt");
        for (var i = 0; i < payload.stages.length; i++) {
            var stage = payload.stages[i];
            var x = i * colSize;
            var y = parseInt("1pt");
            var previous_color = color;
            color = colors[stage.state];

            y = y + rowSize;
            ctx.fillStyle = "black";
            ctx.font = "25pt sans-serif";
            ctx.fillText(stage.name, x + radius / 2, y);

            y = y + radius * 2;

            if (stage.time) {
                ctx.font = "italic 16pt sans-serif";
                ctx.fillText(stage.time, x - colSize / 2, y + 1.5 * radius);
            }

            if (i > 0) {
                var grd = ctx.createLinearGradient(x - colSize, y, x, y);
                grd.addColorStop(0, previous_color);
                grd.addColorStop(3 * radius / colSize, previous_color);
                grd.addColorStop(6 * radius / colSize, color);
                grd.addColorStop(1, color);
                ctx.strokeStyle = grd;
                ctx.fillStyle = grd;

                ctx.beginPath();
                ctx.moveTo(colSize * (i-1) + radius / 2, y);
                ctx.lineTo(x + radius / 2, y);
                ctx.stroke();
            }
            else {
                ctx.strokeStyle = color;
                ctx.fillStyle = color;
            }

            ctx.beginPath();
            ctx.arc(
                x + radius, y,
                radius, 0, 2 * Math.PI
            );
            ctx.fill();

            if (stage.jobs.length) {
                var jobs_height = radius + stage.jobs.length * rowSize;
                var grd = ctx.createLinearGradient(x, y, x, y + jobs_height);
                grd.addColorStop(0, color);
                grd.addColorStop(radius / jobs_height, color);
                ctx.beginPath();
                var job_color = color;
                for (var j = 0; j < stage.jobs.length; j++) {
                    var job_color_previous = job_color;
                    var job = stage.jobs[j];
                    job_color = colors[job.state];
                    grd.addColorStop((rowSize * (1 + j) - job_radius) / jobs_height, job_color);
                    grd.addColorStop(Math.min(1, (rowSize * (1 + j) + job_radius) / jobs_height), job_color);
                    ctx.arc(
                        x + radius, y + rowSize + j * rowSize,
                        job_radius, 0, 2 * Math.PI
                    );
                }
                ctx.fillStyle = grd;
                ctx.fill();

                for (var j = 0; j < stage.jobs.length; j++) {
                    var job = stage.jobs[j];
                    ctx.fillStyle = "black";
                    ctx.font = "20pt sans-serif";
                    ctx.fillText(job.name, x + radius * 2, y + (1 + j) * rowSize + job_radius / 2);
                }

                ctx.strokeStyle = grd;
                ctx.beginPath();
                ctx.moveTo(x + radius, y);
                ctx.lineTo(x + radius, y + rowSize * stage.jobs.length);
                ctx.stroke();
            }
        };
        console.log("Rendering done.");
    },

    headsView: function(repository) {
        var request = new XMLHttpRequest();
        request.open("GET", "/rest/heads/" + repository, true);
        request.onreadystatechange = function() {
            if (4 != this.readyState)
                return;

            try {
                var payload = JSON.parse(this.response);
            }
            catch (err) {
                var payload = {message: "JSON Error: " + err, raw: this.response}
            }

            if (200 != this.status) {
                console.log("Erreur: ", payload);
                return;
            }

            dashboard.context.h1.innerHTML = repository;
            dashboard.context.body.innerHTML = (
                '<section><h>Protected branches</h><ul id="branches"></ul></section>' +
                '<section><h>Recent tags</h><ul id="tags"></ul></section>'
            );
            var brel = document.getElementById('branches');
            payload.branches.forEach(function(item){
                var href = "#!/pipeline/" + repository + "/" + item.ref;
                brel.insertAdjacentHTML('beforeend', (
                    '<li>' +
                    '<p><a href="'+ href + '">' + item.name + '</a></p>' +
                    '</li>'
                ));
            });
            var tagsel = document.getElementById('tags');
            payload.tags.forEach(function(item){
                var href = "#!/pipeline/" + repository + "/" + item.ref;
                tagsel.insertAdjacentHTML('beforeend', (
                    '<li>' +
                    '<p><a href="'+ href + '">' + item.name + '</a></p>' +
                    '</li>'
                ));
            });
        };
        request.send();
    },

    repositoriesView: function() {
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
            if (4 != this.readyState)
                return;

            var payload = JSON.parse(this.response);
            if (200 != this.status) {
                console.log("Erreur: ", payload);
                return;
            }
            dashboard.context.h1.innerHTML = "Repositories";
            dashboard.context.body.innerHTML = '<ul id="repositories"></ul>';
            var reposel = document.getElementById('repositories');
            payload.forEach(function(repo, i){
                var href = "#!/heads/" + repo.owner + "/" + repo.name;
                reposel.insertAdjacentHTML('beforeend', (
                    '<li>' +
                    '<p><a href="'+ href + '">' + repo.owner + '/' + repo.name + '</a></p>' +
                    '<p class="description">' + repo.description_html + '</p>' +
                    '</li>'
                ));
            });
        };
        request.open("GET", "/rest/repositories/", true);
        request.send();
    },
};

function main() {
    dashboard.main();
}
