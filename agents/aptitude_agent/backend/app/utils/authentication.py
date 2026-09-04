from functools import wraps
import uuid
import jwt
from flask import current_app, g, request
from ..extensions import db
from ..models import Student
from .errors import APIError


def require_student(view):
    """Authenticate a JWT issued by AptiDARA and load its registered learner."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_app.config["SINGLE_USER_MODE"]:
            student=db.session.get(Student,current_app.config["LOCAL_USER_ID"])
            if not student:
                student=Student.query.filter_by(email=current_app.config["LOCAL_USER_EMAIL"]).first()
            if not student:
                student=Student.query.order_by(Student.created_at.asc()).first()
            if not student:
                student=Student(id=current_app.config["LOCAL_USER_ID"] or str(uuid.uuid4()),name=current_app.config["LOCAL_USER_NAME"] or "Learner",email=current_app.config["LOCAL_USER_EMAIL"])
                db.session.add(student);db.session.commit()
            g.student=student
            g.auth_claims={"sub":student.id,"mode":"single_user"}
            return view(*args,**kwargs)
        header=request.headers.get("Authorization","")
        if not header.startswith("Bearer "):
            raise APIError("Authentication required",401,"authentication_required")
        try:
            claims=jwt.decode(
                header[7:],current_app.config["JWT_SECRET"],
                algorithms=[current_app.config["JWT_ALGORITHM"]],
                audience=current_app.config["JWT_AUDIENCE"],
                issuer=current_app.config["JWT_ISSUER"],
                options={"require":["sub","exp","iat","aud","iss","ver"]},
            )
            student=db.session.get(Student,str(claims["sub"])[:128])
            if not student or student.token_version!=int(claims["ver"]):
                raise APIError("Invalid or expired session",401,"invalid_token")
            # Strategy F learners are authenticated by the DigiDARA gateway,
            # so their Aptitude mirror intentionally has no second password.
            if claims.get("auth_source")!="strategy_f" and not student.password_hash:
                raise APIError("Invalid or expired session",401,"invalid_token")
        except APIError:
            raise
        except (jwt.PyJWTError,ValueError,TypeError) as exc:
            raise APIError("Invalid or expired session",401,"invalid_token") from exc
        g.student=student
        g.auth_claims=claims
        return view(*args,**kwargs)
    return wrapped
