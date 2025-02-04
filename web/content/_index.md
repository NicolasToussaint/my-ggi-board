---
title: Your Good Governance initiative
layout: default
---

{{% content "includes/initialisation.inc" %}}

This dashboard tracks information from your [GGI board instance]([GGI_ACTIVITIES_URL]). See the [Activity timeline of the project]([GGI_URL]/activity).

Please refer to the [official documentation](https://ospo-alliance.org/ggi).

{{% columns %}}

## General progress

<canvas id="allActivities"></canvas>
 
<script>
data_all_activities = {{% content "includes/ggi_data_all_activities.inc" %}}

data = {
  labels: [
    'Not Started (' + data_all_activities[0] + ')',
    'In Progress (' + data_all_activities[1] + ')',
    'Completed  (' + data_all_activities[2] + ')',
  ],
  datasets: [{
    label: 'My activities',
    data: data_all_activities,
    backgroundColor: [
      'rgb(255, 99, 132)',
      'rgb(54, 162, 235)',
      'rgb(255, 205, 86)'
    ],
    hoverOffset: 4
  }]
};
new Chart("allActivities", {
    type: "doughnut",
    data: data,
    options:{
        plugins:{
            legend:{
                position: "bottom"
            }
        },
        responsive: true,
        maintainAspectRatio: false
    }
});
</script>

<--->

## Goals

<canvas id="myGoals" style="width:50%;height:50%"></canvas>
<script>
labels = ['Usage', 'Trust', 'Culture', 'Engagement', 'Strategy'];
data = {
  labels: labels,
  datasets: [
    {
      label: 'Done',
      data: {{% content "includes/ggi_data_goals_done.inc" %}},
      backgroundColor: 'rgb(255, 205, 86)',
    },
    {
      label: 'In Progress',
      data: {{% content "includes/ggi_data_goals_in_progress.inc" %}},
      backgroundColor: 'rgb(54, 162, 235)',
    },
    {
      label: 'Not Started',
       data: {{% content "includes/ggi_data_goals_not_started.inc" %}},
      backgroundColor: 'rgb(255, 99, 132)',
    },
  ]
};
new Chart("myGoals", {
    type: 'bar',
    data: data,
    options: {
        plugins:{
            legend:{
                position: "bottom"
            }
        },
        responsive: true,
        scales: {
            x: {
                stacked: true
            },
            y: {
                stacked: true
            }
        }
    }
  }
);

</script>

{{% /columns %}}

## Activities <a href='scorecards/' class='w3-text-grey' style="float:right">[ details ]</a> 

<script>
var dataSet = {{% jscontent "includes/activities.js.inc" %}}

$(document).ready(function () {
    $('#activities').DataTable({
        data: dataSet,
        order: [[1, 'asc']],
        pageLength: 25,
        lengthMenu: [
            [10, 25, 50, -1],
            [10, 25, 50, 'All'],
        ],
        columns: [
            { title: 'ID',
                render: function (data, type, row, meta) {
                    if (type === 'display'){
                        activity_id = row[0].toLowerCase();
                        link = "scorecards/activity_" +activity_id;
                        return '<a href="' + link + '">' + data + '</a>';
                    }
                    else{
                        return data;
                    }
                }
            },
            { title: 'Status' },
            { title: 'Title',
                render: function (data, type, row, meta) {
                    if (type === 'display'){
                        activity_id = row[0].toLowerCase();
                        link = "scorecards/activity_" +activity_id;
                        return '<a href="' + link + '">' + data + '</a>';
                    }
                    else{
                        return data;
                    }
                }
            },
            { title: 'Tasks',
                render: function (data, type, row, meta) {
                    return type === 'display' ?
                        row[3] + '/' + row[4] : "";
                },
            },
            { 
                title: 'Completion',
                render: function (data, type, row, meta) {
                    let completion = "0%";
                    let done = row[3];
                    let total = row[4];
                    if (total > 0){
                        completion = Math.round(done/total*100);
                    }
                    if (type === 'display'){
                        if (completion > 0){
                            return '<div class="w3-light-grey w3-round"><div class="w3-container w3-blue w3-round" style="width:' + completion + '%">' + completion + '%</div></div>';
                        }
                        else{
                            return '<div class="w3-light-grey w3-round">0%</div>';
                        }
                    }
                    else{
                        return data;
                    }
                },
            }
        ],
    });
});
</script>
<table id="activities" class="display" width="100%"></table>

## Resources

The [Good Governance Initiative](https://ospo-alliance.org/ggi) is developed by the OSPO Alliance.

Check [our website](https://ospo-alliance.org) and [join the discussion](https://accounts.eclipse.org/mailing-list/ospo.zone)!
