from app import db
import datetime


class User(db.Model):
    """User model for authentication and identification"""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    forename = db.Column(db.Unicode(32))
    surname = db.Column(db.Unicode(32))
    username = db.Column(db.String(128), unique=True)

    @property
    def name(self):
        # display full name of user
        return self.forename + " " + self.surname

    def create_goal(self, text):
        # check some text has been entered
        if not text.strip():
            raise ValueError("Goals must have some text")

        goal = Goal(text=text)
        self.goals.append(goal)
        return goal


class Goal(db.Model):
    """Big overall goals for individual users, comprising of actions"""

    __tablename__ = "goal"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow())
    completed = db.Column(db.DateTime)
    percentage_complete = db.Column(db.SmallInteger, default=0)
    text = db.Column(db.Unicode(512), nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref(
            "goals",
            order_by="Goal.created",
            cascade="all,delete-orphan",
            lazy="dynamic",
        ),
    )

    def create_action(self, text):
        # check some text has been entered
        if not text.strip():
            raise ValueError("Actions must have some text")

        action = GoalAction(text=text)
        self.actions.append(action)
        db.session.flush()  # in case refresh_percentage_complete uses further queries

        self.refresh_percentage_complete()

        return action

    def mark_as_complete(self):
        self.completed = datetime.datetime.utcnow()

    def unmark_as_complete(self):
        self.completed = None

    @property
    def base_actions(self):
        # fetch non-nested actions
        return self.actions.filter(GoalAction.parent_action_id == None)

    def refresh_percentage_complete(self):

        total_actions = 0
        completed_actions = 0

        for action in self.actions:
            if not action.parent_action:
                #print("Top level action found. Adding one to total actions...")
                total_actions += 1

                if action.completed != None:
                    #print("Top level action completed. Adding one to completed actions...")
                    completed_actions +=1

                else:
                    #print("Top level action incomplete. Search percentage of completeness...")
                    completed_actions += action.calc_completeness_ptge()                    

        if total_actions > 0 and total_actions >= completed_actions:
            print("Completeness percentage: ", completed_actions*100/total_actions)        
            self.percentage_complete = int(completed_actions*100/total_actions)
        
            if self.percentage_complete == 100 and completed_actions > 0: 
                print("Goal completed!")
                self.mark_as_complete() 
            else: 
                #print("Goal incomplete")
                self.unmark_as_complete() 
        
        return self.percentage_complete
    

    def delete_goal(self):
        db.session.delete(self)


class GoalAction(db.Model):
    """Actions & nested sub-actions for goals"""

    __tablename__ = "goalaction"

    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("goal.id"), nullable=False)
    parent_action_id = db.Column(db.Integer, db.ForeignKey("goalaction.id"))
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow())
    completed = db.Column(db.DateTime)
    text = db.Column(db.Unicode(512), nullable=False)

    goal = db.relationship(
        "Goal",
        backref=db.backref(
            "actions",
            order_by="GoalAction.created",
            cascade="all,delete-orphan",
            lazy="dynamic",
        ),
    )
    parent_action = db.relationship(
        "GoalAction",
        remote_side="GoalAction.id",
        foreign_keys="GoalAction.parent_action_id",
        backref=db.backref(
            "child_actions",
            remote_side="GoalAction.parent_action_id",
            cascade="all,delete-orphan",
            order_by="GoalAction.created",
        ),
    )

    def create_subaction(self, text):
        # check some text has been entered
        if not text.strip():
            raise ValueError("Actions must have some text")

        action = GoalAction(text=text, goal=self.goal)
        self.child_actions.append(action)
        db.session.flush()  # in case refresh_percentage_complete uses further queries

        self.goal.refresh_percentage_complete()
        return action

    # TODO - 1
    def mark_as_complete(self):
        #print("***** Marking action completed *****")

        if self.child_actions:
            #print(f"Found {len(self.child_actions)} subactions!")
            for subaction in self.child_actions:
                if subaction.completed == None:
                    raise ValueError("You must complete every subaction")

        #print("No subaction found, updating action status to completed...")
        self.completed = datetime.datetime.utcnow() 

    def update_complete(self):  

        print(f"Action {self.text} completed!")      
        if not self.parent_action:
            pass
            #print("No parent action found")
        
        elif len(self.parent_action.child_actions) > 1:
            #print("Checking if parent action is completed...")
            nr_brotheractions_completed = 1
            for brotheraction in self.parent_action.child_actions:
                
                #print(brotheraction.text)
                if brotheraction is not self:
                    if brotheraction.completed != None:
                        #print("Same level subaction found!")
                        nr_brotheractions_completed += 1                        
                    else:
                        #print("There are same level subactions yet to complete.")
                        pass                         
                        
            #print("Brother actions: ", nr_brotheractions_completed)
            #print(len(self.parent_action.child_actions))
            if nr_brotheractions_completed == len(self.parent_action.child_actions):
                self.parent_action.completed = datetime.datetime.utcnow()
                self.parent_action.update_complete()            

        elif len(self.parent_action.child_actions) == 1:
            #print("No other same level subactions found, parent action completed!")
            self.parent_action.completed = datetime.datetime.utcnow()
            self.parent_action.update_complete()
        
        self.goal.refresh_percentage_complete()
    
    def unmark_as_complete(self):    
        #print("***** Unmarking completed action *****") 
        nr_not_completed_actions = 0       

        if self.child_actions:
            #print(f"Found {len(self.child_actions)} subactions!")
            for subaction in self.child_actions:                
                if subaction.completed == None:
                    #print("Not completed subaction found...")
                    nr_not_completed_actions +=1
            if nr_not_completed_actions == 0:
                raise ValueError("You must unmark at least one subaction")

            #print(f"Found {nr_not_completed_actions} not completed subactions, updating action status to incompleted...") 
        else:             
            #print(f"No subactions found, updating action {self.text} status to incomplete...") 
            pass

        self.completed = None
        self.goal.refresh_percentage_complete()

    def update_incomplete(self):  

        print(f"Action {self.text} incomplete!")      
        if not self.parent_action:
            #print(f"No parent action found. Action: {self.text} completness status is {self.completed}")
            pass
        
        elif len(self.parent_action.child_actions) > 1:
            #print("Checking if parent action is incomplete...")
            for brotheraction in self.parent_action.child_actions:
                if brotheraction is not self:
                    if brotheraction.completed != None:
                        #print("At least one subaction incomplete! Parent action is also incomplete!")
                        self.parent_action.completed = None
                        self.parent_action.update_incomplete()
                    else:
                        #print("All same level subactions completed.")
                        pass

        elif len(self.parent_action.child_actions) == 1:
            #print("No other same level subactions found, parent action incomplete!")
            self.parent_action.completed = None
            self.parent_action.update_incomplete()
        
        self.goal.refresh_percentage_complete()

    def calc_completeness_ptge(self):

        total_actions = 0
        completed_actions = 0

        for child in self.child_actions:            
            total_actions +=1
            if child.completed != None:
                completed_actions +=1
            else: 
                completed_actions += child.calc_completeness_ptge()

        if total_actions == 0: return 0
        else: return completed_actions/total_actions

    def delete_action(self):
        goal = self.goal

        if len(self.goal.actions.all()) == 1:
            goal.unmark_as_complete()            

        self.goal.actions.remove(self)

        # db.session.delete(self)
        db.session.flush()  # in case refresh_percentage_complete uses further queries        

        goal.refresh_percentage_complete()