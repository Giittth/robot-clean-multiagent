



// 准备要发送的数据，格式是 JavaScript 对象
const newUser = {
    username: "alice123",
    password: "my_secret_pw"
};

fetch("http://localhost:8000/register",{
    method : "POST",
    headers : {
        "content-type" : "application/json",
    },
    body: JSON.stringify(newUser)
    }
)
.then(response => response.json())
.then(data => {
    console.log("后端返回的数据:", data);
});



