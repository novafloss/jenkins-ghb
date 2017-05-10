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
        this.context.body.innerHTML = '<p id="patiente">…</p>';
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

    get: function(url, callback) {
        var request = new XMLHttpRequest();
        request.open("GET", url, true);
        request.onreadystatechange = function() {
            var payload;
            if (4 != this.readyState)
                return;

            try {
                payload = JSON.parse(this.response);
            }
            catch (err) {
                payload = {message: "JSON Error: " + err, raw: this.response};
            }

            if (200 != this.status) {
                console.log("Erreur: ", payload);
                return;
            }
            callback(payload);
        };
        request.send();
    },

    pipelineView: function(path) {
        this.get("/rest/pipeline/" + path, function(payload) {
            dashboard.context.h1.innerHTML = (
                '<span class="head">' +
                payload.repository.owner + '/' + payload.repository.name +
                ' @' + payload.ref +
                '</span>'
            );
            dashboard.context.body.innerHTML = (
                '<table id="statuses"></table>' +
                '<canvas id="pipeline"></canvas>'
            );
            var table = document.getElementById('statuses');
            dashboard.fillStatuses(table, payload);
            var canvas = document.getElementById('pipeline');
            dashboard.drawPipeline(
                table, canvas,
                parseInt(window.getComputedStyle(document.querySelector('#body')).width),
                payload
            );
            window.addEventListener('resize', function() {
                dashboard.drawPipeline(
                    table, canvas,
                    parseInt(window.getComputedStyle(document.querySelector('#body')).width),
                    payload
                );
            });
        });
        window.setTimeout(function() {
            window.location.reload();
        }, 300 * 1000);
    },

    fillStatuses: function(table, payload) {
        var max = 0;
        var i;
        for (i = 0; i < payload.stages.length; i++) {
            max = Math.max(max, payload.stages[i].statuses.length);
        }
        var j;
        var row;
        var cell;
        var name;
        var status;
        for (i = 0; i < max; i++) {
            row = table.insertRow(-1);
            for (j = 0; j < payload.stages.length; j++) {
                cell = row.insertCell(-1);
                status = payload.stages[j].statuses[i];
                if (status == undefined) {
                    continue;
                }
                name = status.name;
                cell.innerHTML = "<nobr>" + name + "</nobr>";
                cell.attributes.className = "status " + status.state;
            }
        }
    },

    drawPipeline: function(table, canvas, max_width, payload) {
        var tableOffset = table.offsetTop - canvas.offsetTop;
        var em = tableOffset / 4;
        canvas.width = max_width;
        canvas.height = table.offsetTop + table.offsetHeight - canvas.offsetTop;
        var ctx = canvas.getContext("2d");
        var count = payload.stages.length;
        var colors = {
            'success': "rgb(108, 198, 68)",
            'pending': 'rgb(206, 166, 27)',
            'error': '#BD2C00',
            'failure': '#BD2C00',
            'unknown': '#9E9E9E'
        };
        var color = '';
        var grd;
        var colSize = canvas.offsetWidth / count;
        var radius = em;
        var radius_job = .65 * radius;
        for (var i = 0; i < payload.stages.length; i++) {
            var stage = payload.stages[i];
            var x = i * colSize;
            var y = .1 * em;
            var previous_color = color;
            color = colors[stage.state];

            y = y + 1.2 * em;
            ctx.fillStyle = "black";
            ctx.font = "1.2em sans-serif";
            ctx.fillText(stage.name, x + radius / 2, y);

            y = y + radius * 1.5;
            // Draw main pipeline step.
            if (i > 0) {
                grd = ctx.createLinearGradient(x - colSize, y, x, y);
                grd.addColorStop(0, previous_color);
                grd.addColorStop(.6, previous_color);
                grd.addColorStop(Math.min(.8, 1 - radius / colSize), color);
                grd.addColorStop(1, color);
                ctx.strokeStyle = grd;
                ctx.fillStyle = grd;

                ctx.beginPath();
                ctx.moveTo(colSize * (i - 1) + radius / 2, y);
                ctx.lineTo(x + radius / 2, y);
                ctx.lineWidth = .75 * em;
                ctx.stroke();
            }
            else {
                ctx.strokeStyle = color;
                ctx.fillStyle = color;
            }

            ctx.beginPath();
            ctx.arc(x + radius, y, radius, 0, 2 * Math.PI);
            ctx.fill();

            y = tableOffset;
            var cell;
            if (stage.statuses.length) {
                var jobs_height = table.rows[0].cells[i].offsetHeight;
                var circle_height = radius_job * 2;
                var stage_height = jobs_height * stage.statuses.length;
                grd = ctx.createLinearGradient(x, y, x, y + stage_height);
                grd.addColorStop(0, color);
                ctx.beginPath();
                // Draw all bubbles and define global stage gradiant.
                for (var j = 0; j < stage.statuses.length; j++) {
                    var job = stage.statuses[j];
                    var job_color = colors[job.state];
                    cell = table.rows[j].cells[i];
                    var color_pad = (cell.offsetHeight - circle_height) / 2;
                    var stop0 = cell.offsetTop + color_pad;
                    var stop1 = cell.offsetTop + cell.offsetHeight - color_pad;
                    grd.addColorStop(stop0 / stage_height, job_color);
                    grd.addColorStop(Math.min(1, stop1 / stage_height), job_color);
                    ctx.arc(
                        x + radius, y + cell.offsetTop + cell.offsetHeight / 2,
                        radius_job, 0, 2 * Math.PI
                    );
                }
                ctx.fillStyle = grd;
                ctx.fill();

                // Draw vertical line up to last bubble.
                ctx.beginPath();
                ctx.moveTo(x + radius, y - radius);
                ctx.lineTo(x + radius, y + cell.offsetTop + cell.offsetHeight / 2);
                ctx.strokeStyle = grd;
                ctx.lineWidth = .5 * em;
                ctx.stroke();
            }
        };
    },

    headsView: function(repository) {
        this.get("/rest/heads/" + repository + "/", function(payload) {
            dashboard.context.h1.innerHTML = repository;
            dashboard.context.body.innerHTML = (
                '<section><h>Protected branches</h><ul id="branches"></ul></section>'
            );
            var brel = document.getElementById('branches');
            payload.branches.forEach(function(item){
                var href = "#!/pipeline/" + repository + "/" + item.fullref;
                brel.insertAdjacentHTML('beforeend', (
                    '<li><p><a href="'+ href + '">' + item.name + '</a></p></li>'
                ));
            });
            var tagsel = document.getElementById('tags');
            payload.tags.forEach(function(item){
                var href = "#!/pipeline/" + repository + "/" + item.fullref;
                tagsel.insertAdjacentHTML('beforeend', (
                    '<li><p><a href="'+ href + '">' + item.name + '</a></p></li>'
                ));
            });
        });
    },

    repositoriesView: function() {
        this.get("/rest/repositories/", function(payload) {
            dashboard.context.h1.innerHTML = "Repositories";
            dashboard.context.body.innerHTML = '<ul id="repositories"></ul>';
            var reposel = document.getElementById('repositories');
            payload.forEach(function(repo, i){
                var href = "#!/heads/" + repo.owner + "/" + repo.name;
                reposel.insertAdjacentHTML('beforeend', (
                    '<li><p><a href="'+ href + '">' + repo.name + '</a></p></li>'
                ));
            });
        });
    }
};

function main() {
    dashboard.main();
}
