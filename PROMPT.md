You are designing and building Spoonfeed, a task management tool. Spoonfeed is intended both for day-to-day use for tracking immediate tasks, and for tracking long term projects. Spoonfeed should be written in Python and should use a SQLite database on the backend.

Features
Features are listed by importance. Implement the features appearing earlier in full before working on the features appearing later.
- creating tasks
	The user should be able to create a task by pressing “n” on the keyboard. They should be prompted to provide a name for the task. The name of the task and the datetime of its creation should be saved to the database. Pressing “enter” should end the process and create the task.
- viewing tasks
	The main screen of the app should be a list of the currently visible tasks (tasks may not be visible for reasons discussed below). They should be displayed as a list sorted by creation date.
- editting tasks
	The user should be able to edit a given task by double clicking on it to bring up a popup similar to the “create new task” popup that allows them to edit the name and other information associated with the task. Double-clicking a task should pull up its edit menu.
- checking tasks off
	The user should be able to check tasks off. This should not delete them from the database, merely mark them as checked off and save the datetime at which they were checked off. Tasks should not be visible after they are checked off. Each task should have a check off button associated with it on the main screen.
- deleting tasks
	The user should be able to delete tasks. Checking a deleting a task is almost the same as checking it off, except that it should be stored as deleted rather than checked off. Holding shift should turn all check off buttons into delete buttons on the main screen.
- task notes
	The user should be able to record notes about each task. These should be optional but should be editable in the create menu and the edit menu.
- defer dates
	The user should be able to specify a defer datetime for each task (upon creation or edit of the task). By default, a task should not display until the current datetime is past its defer datetime. If a defer datetime is not specified when a task is created, the current datetime should be used. There should be a button associated with each task that changes the defer datetime of that task to an hour from the current datetime. Holding shift should change this button to one that moves the defer datetime to the next midnight.
- repeating tasks
	By default, tasks should not be repeating, but the user should be able to specify a repeat interval and a repeat start datetime to create a repeating task. Repeating tasks should behave as if the user had created an infinite number of tasks where the first one had a defer datetimeof the start datetime, the next had a defer datetime of the start datetime plus the repeat interval, the third had a defer datetime of the start datetime plus two times the repeat interval, and so on. Editing or deleting any one of these apparently infinite instances should edit or delete all of them.
- subtasks
	When creating or editing a task, the user should be able to specify a parent task. A parent task cannot be checked off or deleted until all of its subtasks are. Subtasks should be displayed in an indented block under the parent tasks. Nested subtasks are allowed. A child should not display if its parent is hidden for any reason. A repeating task cannot be a parent or child task. The user should also be able to create a subtask with an existing task as the parent by clicking a button on the parent task. If a shown parent task has hidden child tasks, the number of hidden child tasks should be shown at the bottom of the list of shown children
- sequential tasks
	When creating or editing a task, the user should be able to specify an existing task (in a similar way to specifying a parent task). This task will become the task’s predecessor. The task should not display until its predecessor is checked off or deleted (in addition to not displaying until its defer datetime). It must never be the case that a task's parent (or any successor of that tasks’s parent) is a task’s predecesor. Predecessor/successor relationships must remain acyclic. 
- undo and redo
	The user should be able to undo and redo actions with cmd+z and cmd+shift+z.
- previewing future days/times, other view options
	There should be a small bar at the top of the screen that specifies how to view the tasks. There should be an option to view tasks as if in some point in the past or future. There should be an option to show successor tasks. There should also be an option to display recently checked off and deleted tasks, with a datetime picker for what qualifies as “recently”.
- due date (the date past which it cannot be deferred)
	The user should be able to specify a due date for a task. The user should not be able to perform any action that would make a task hidden by default on its due date. This means that the due dates of all children must be checked when deferring a parent task, and the due dates of all successors must be checked when deferring a predecessor task.
