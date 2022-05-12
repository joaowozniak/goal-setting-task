from flask import (
    render_template,
    g,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    abort,
)
from sqlalchemy.orm.exc import NoResultFound

from app import db
from app.auth import login_required
from app.goals import goals
from app.models import User, Goal, GoalAction


@goals.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        # handle new goal creation
        new_goal_text = request.form["new_goal_text"]

        try:
            new_goal = g.current_user.create_goal(text=new_goal_text)
        except ValueError as ie:
            return jsonify({"result": "error", "message": str(ie)})
        else:
            db.session.commit()
            flash("Created new goal!")
            return jsonify(
                {
                    "result": "ok",
                    "action": "redirect",
                    "redirect_url": url_for("goals.view_goal", goal_id=new_goal.id),
                }
            )

    goals = Goal.query.filter_by(user_id=g.current_user.id).order_by(
        Goal.completed.desc(), Goal.created.desc()
    )
    return render_template("home.html", goals=goals)


@goals.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # handle login

        user_id = request.form["user"]

        try:
            user = User.query.filter_by(id=user_id).one()
        except NoResultFound:
            flash("Oops - that user does not exist anymore. Try another.")

        else:
            session["active_user"] = user.id
            flash("Logged in as {}".format(user.name))
            return redirect(url_for("goals.home"))

    return render_template("login.html", users=User.query.order_by(User.username))


@goals.route("/goal/<goal_id>", methods=["GET", "POST"])
@login_required
def view_goal(goal_id):
    try:
        goal = Goal.query.filter_by(id=goal_id, user_id=g.current_user.id).one()
    except NoResultFound:
        abort(404)

    if request.method == "POST":
        # handle action tasks
        task = request.form["task"]

        if task == "create_action":
            if request.form["base_action_id"] == "_base":
                # add base action
                try:
                    goal.create_action(text=request.form["new_action_text"])                    
                except ValueError as ve:
                    return jsonify(
                        {
                            "result": "error",
                            "message": "Invalid action - {}".format(str(ve)),
                        }
                    )

            else:
                # add nested sub-action
                # fetch action to nest sub-action under
                try:
                    base_action = GoalAction.query.filter(
                        GoalAction.id == request.form["base_action_id"],
                        GoalAction.goal_id == goal.id,
                    ).one()
                except NoResultFound:
                    return jsonify({"result": "error", "message": "Invalid action"})

                try:
                    base_action.create_subaction(text=request.form["new_action_text"])
                    base_action.update_incomplete()
                except ValueError as ve:
                    return jsonify(
                        {
                            "result": "error",
                            "message": "Invalid action - {}".format(str(ve)),
                        }
                    )                

            db.session.commit()
            return jsonify({"result": "ok"})

        elif task == "delete_goal":
            goal.delete_goal()

            db.session.commit()
            return jsonify({"result": "ok"})

        elif task in [
            "delete_action",
            "mark_action_as_complete",
            "unmark_action_as_complete",
        ]:

            # fetch action
            try:
                action = GoalAction.query.filter(
                    GoalAction.id == request.form["action_id"],
                    GoalAction.goal_id == goal.id,
                ).one()
            except NoResultFound:
                return jsonify({"result": "error", "message": "Invalid action"})

            # run task
            if task == "delete_action":
                try:
                    action.delete_action()  
                except ValueError as ve:
                    return jsonify(
                        {
                            "result": "error",
                            "message": "Invalid action - {}".format(str(ve)),
                        }
                    )                               

            elif task == "mark_action_as_complete":
                try:
                    action.mark_as_complete()
                    action.update_complete()
                except ValueError as ve:
                    return jsonify(
                        {
                            "result": "error",
                            "message": "Invalid action - {}".format(str(ve)),
                        }
                    )                

            elif task == "unmark_action_as_complete":                
                try:
                    action.unmark_as_complete()
                    action.update_incomplete()
                except ValueError as ve:
                    return jsonify(
                        {
                            "result": "error",
                            "message": "Invalid action - {}".format(str(ve)),
                        }
                    ) 

            db.session.commit()
            return jsonify({"result": "ok"})

        else:
            # unrecognised task
            abort(400)

    return render_template("view_goal.html", goal=goal)


@goals.route("/logout")
def logout():
    try:
        # remove user_id from session
        session.pop("active_user")
    except KeyError:
        pass
    return redirect(url_for("goals.login"))
